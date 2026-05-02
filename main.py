import os
import asyncio
import logging
import aiosqlite

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
STAFF_CHANNEL_ID = os.getenv("STAFF_CHANNEL_ID")


class ApplicationsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()

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

        async with aiosqlite.connect("applications.db") as db:
            cursor = await db.execute(
                """
                INSERT INTO applications (
                    discord_user_id,
                    discord_username,
                    minecraft_nick,
                    age,
                    experience,
                    reason,
                    rules_agreement,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    interaction.user.id,
                    str(interaction.user),
                    str(self.minecraft_nick),
                    str(self.age),
                    str(self.experience),
                    str(self.reason),
                    str(self.rules_agreement),
                ),
            )
            await db.commit()
            application_id = cursor.lastrowid

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

        view = ApplicationReviewView()
        await staff_channel.send(embed=embed, view=view)

        await interaction.followup.send(
            "Заявка отправлена администрации на рассмотрение.",
            ephemeral=True,
        )


class ApplicationReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

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
            f"Заявка отмечена как: {status_text}",
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
    await interaction.response.send_modal(ApplicationModal())


async def init_db():
    async with aiosqlite.connect("applications.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_user_id INTEGER NOT NULL,
                discord_username TEXT NOT NULL,
                minecraft_nick TEXT NOT NULL,
                age TEXT,
                experience TEXT,
                reason TEXT,
                rules_agreement TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def main():
    if DISCORD_TOKEN is None:
        raise RuntimeError("DISCORD_TOKEN не указан в .env")

    await init_db()
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
