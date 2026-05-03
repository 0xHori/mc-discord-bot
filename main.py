import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    DISCORD_TOKEN,
    GUILD_ID,
    STAFF_CHANNEL_ID,
    ACCEPTED_ROLE_ID,
)

from database import (
    init_db,
    create_application,
    set_staff_message_id,
    get_application_status,
    update_application_status,
    create_moderation_decision,
    get_application_user_id,
    get_latest_application_by_user,
)


class ApplicationsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self):
        if GUILD_ID is None:
            raise RuntimeError("GUILD_ID не указан в .env")

        guild = discord.Object(id=int(GUILD_ID))

        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

        logging.info("Slash команды синхронизированы для гильдии %s", GUILD_ID)


bot = ApplicationsBot()


class ApplicationModal(discord.ui.Modal, title="Заявка на сервер"):
    minecraft_nick = discord.ui.TextInput(
        label="Minecraft ник",
        placeholder="Например: 0xHori",
        max_length=32,
        required=True,
    )

    age = discord.ui.TextInput(
        label="Возраст",
        placeholder="Например: 18",
        max_length=3,
        required=True,
    )

    experience = discord.ui.TextInput(
        label="Опыт игры",
        placeholder="Расскажи, как давно играешь и на каких серверах был",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    reason = discord.ui.TextInput(
        label="Почему хочешь попасть на сервер?",
        placeholder="Коротко объясни мотивацию",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True,
    )

    rules_agreement = discord.ui.TextInput(
        label="Согласен с правилами?",
        placeholder="Да / Нет",
        max_length=20,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        application_id = await create_application(
            discord_user_id=interaction.user.id,
            discord_username=str(interaction.user),
            minecraft_nick=str(self.minecraft_nick),
            age=str(self.age),
            experience=str(self.experience),
            reason=str(self.reason),
            rules_agreement=str(self.rules_agreement),
        )

        if STAFF_CHANNEL_ID is None:
            await interaction.followup.send(
                "Ошибка конфигурации: staff-канал не указан.",
                ephemeral=True,
            )
            return

        staff_channel = interaction.client.get_channel(int(STAFF_CHANNEL_ID))

        if staff_channel is None:
            await interaction.followup.send(
                "Ошибка: staff-канал не найден. Проверь STAFF_CHANNEL_ID.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"Новая заявка #{application_id}",
            description="Статус: На рассмотрении",
            color=discord.Color.orange(),
        )

        embed.add_field(
            name="Игрок",
            value=f"{interaction.user.mention} (`{interaction.user.id}`)",
            inline=False,
        )

        embed.add_field(
            name="Minecraft ник",
            value=str(self.minecraft_nick),
            inline=False,
        )

        embed.add_field(
            name="Возраст",
            value=str(self.age),
            inline=False,
        )

        embed.add_field(
            name="Опыт игры",
            value=str(self.experience),
            inline=False,
        )

        embed.add_field(
            name="Почему хочет попасть",
            value=str(self.reason),
            inline=False,
        )

        embed.add_field(
            name="Согласие с правилами",
            value=str(self.rules_agreement),
            inline=False,
        )

        embed.set_footer(
            text=f"Application ID: {application_id} | User ID: {interaction.user.id}"
        )

        view = ApplicationReviewView(application_id=application_id)
        staff_message = await staff_channel.send(embed=embed, view=view)

        await set_staff_message_id(
            application_id=application_id,
            staff_message_id=staff_message.id,
        )

        await interaction.followup.send(
            "Заявка отправлена администрации на рассмотрение.",
            ephemeral=True,
        )


class ApplicationReviewView(discord.ui.View):
    def __init__(self, application_id: int):
        super().__init__(timeout=None)
        self.application_id = application_id

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success)
    async def accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.process_decision(interaction, "accepted")

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger)
    async def reject(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.process_decision(interaction, "rejected")

    async def process_decision(
        self,
        interaction: discord.Interaction,
        decision: str,
    ):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send(
                "У тебя нет прав для обработки заявок.",
                ephemeral=True,
            )
            return

        row = await get_application_status(self.application_id)

        if row is None:
            await interaction.followup.send(
                "Заявка не найдена в базе данных.",
                ephemeral=True,
            )
            return

        current_status = row[0]

        if current_status != "pending":
            await interaction.followup.send(
                f"Эта заявка уже обработана. Текущий статус: {current_status}",
                ephemeral=True,
            )
            return

        await update_application_status(self.application_id, decision)

        await create_moderation_decision(
            application_id=self.application_id,
            moderator_id=interaction.user.id,
            moderator_username=str(interaction.user),
            decision=decision,
        )

        if decision == "accepted":
            if ACCEPTED_ROLE_ID is None:
                await interaction.followup.send(
                    "Заявка принята, но ACCEPTED_ROLE_ID не указан в .env.",
                    ephemeral=True,
                )
                return

            role = interaction.guild.get_role(int(ACCEPTED_ROLE_ID))

            if role is None:
                await interaction.followup.send(
                    "Заявка принята, но роль для выдачи не найдена.",
                    ephemeral=True,
                )
                return

            cursor_user_id = await get_application_user_id(self.application_id)

            member = interaction.guild.get_member(cursor_user_id)

            if member is None:
                try:
                    member = await interaction.guild.fetch_member(cursor_user_id)
                except discord.NotFound:
                    await interaction.followup.send(
                        "Заявка принята, но пользователь не найден на сервере.",
                        ephemeral=True,
                    )
                    return

            await member.add_roles(
                role,
                reason=f"Заявка #{self.application_id} принята модератором {interaction.user}",
            )

        embed = interaction.message.embeds[0]

        status_text = "Принята" if decision == "accepted" else "Отклонена"
        color = discord.Color.green() if decision == "accepted" else discord.Color.red()

        embed.color = color
        embed.description = f"Статус: {status_text}"
        embed.add_field(
            name="Решение",
            value=f"{status_text} модератором {interaction.user.mention}",
            inline=False,
        )

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(embed=embed, view=self)

        await interaction.followup.send(
            f"Заявка #{self.application_id} отмечена как: {status_text}",
            ephemeral=True,
        )

@bot.event
async def on_ready():
    logging.info("Бот активирован: %s", bot.user)


@bot.tree.command(name="ping", description="Проверить, что бот онлайн")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send("Понг!", ephemeral=True)


@bot.tree.command(name="apply", description="Подать заявку на сервер")
async def apply(interaction: discord.Interaction):
    latest_application = await get_latest_application_by_user(interaction.user.id)

    if latest_application is not None:
        application_id, status, created_at = latest_application

        if status == "pending":
            await interaction.response.send_message(
                f"У тебя уже есть заявка #{application_id} на рассмотрении.",
                ephemeral=True,
            )
            return

        if status == "accepted":
            await interaction.response.send_message(
                f"Твоя заявка #{application_id} уже была принята.",
                ephemeral=True,
            )
            return

    await interaction.response.send_modal(ApplicationModal())


async def main():
    if DISCORD_TOKEN is None:
        raise RuntimeError("DISCORD_TOKEN не указан в .env")

    await init_db()
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
