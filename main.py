import os
import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")


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
        await interaction.response.send_message(
            "Заявка получена. Позже она будет отправляться администрации.",
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


async def main():
    if DISCORD_TOKEN is None:
        raise RuntimeError("DISCORD_TOKEN не указан в .env")

    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
