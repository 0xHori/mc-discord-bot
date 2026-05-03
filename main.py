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
ACCEPTED_ROLE_ID = os.getenv("ACCEPTED_ROLE_ID")


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

        view = ApplicationReviewView(application_id=application_id)
        staff_message = await staff_channel.send(embed=embed, view=view)

        async with aiosqlite.connect("applications.db") as db:
            await db.execute(
                """
                UPDATE applications
                SET staff_message_id = ?
                WHERE id = ?
                """,
                (staff_message.id, application_id),
            )
            await db.commit()

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

        async with aiosqlite.connect("applications.db") as db:
            cursor = await db.execute(
                """
                SELECT status
                FROM applications
                WHERE id = ?
                """,
                (self.application_id,),
            )
            row = await cursor.fetchone()

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

            await db.execute(
                """
                UPDATE applications
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (decision, self.application_id),
            )

            await db.execute(
                """
                INSERT INTO application_decisions (
                    application_id,
                    moderator_id,
                    moderator_username,
                    decision
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    self.application_id,
                    interaction.user.id,
                    str(interaction.user),
                    decision,
                ),
            )

            await db.commit()

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


async def get_application_user_id(application_id: int) -> int:
    async with aiosqlite.connect("applications.db") as db:
        cursor = await db.execute(
            """
            SELECT discord_user_id
            FROM applications
            WHERE id = ?
            """,
            (application_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise ValueError(f"Application #{application_id} not found")

    return int(row[0])


async def get_latest_application_by_user(discord_user_id: int):
    async with aiosqlite.connect("applications.db") as db:
        cursor = await db.execute(
            """
            SELECT id, status, created_at
            FROM applications
            WHERE discord_user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (discord_user_id,),
        )
        row = await cursor.fetchone()

    return row


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
                staff_message_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS application_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                moderator_username TEXT NOT NULL,
                decision TEXT NOT NULL,
                comment TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (application_id) REFERENCES applications (id)
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
