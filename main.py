import asyncio
import logging

import discord
from discord.ext import commands

from config import DISCORD_TOKEN, GUILD_ID
from database import init_db


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

        await self.load_extension("cogs.applications")

        guild = discord.Object(id=int(GUILD_ID))

        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

        logging.info("Slash команды синхронизированы для гильдии %s", GUILD_ID)


bot = ApplicationsBot()


@bot.event
async def on_ready():
    logging.info("Бот активирован: %s", bot.user)


async def main():
    if DISCORD_TOKEN is None:
        raise RuntimeError("DISCORD_TOKEN не указан в .env")

    await init_db()
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())