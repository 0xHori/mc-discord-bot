import asyncio
import logging

import discord
from discord.ext import commands

from config import DISCORD_TOKEN, GUILD_ID
from database import init_db, get_latest_application_by_user
from modals.application_modal import ApplicationModal


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