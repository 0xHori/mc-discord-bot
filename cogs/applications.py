import discord
from discord import app_commands
from discord.ext import commands

from database import get_latest_application_by_user
from modals.application_modal import ApplicationModal


class ApplicationsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Проверить, что бот онлайн")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Понг!", ephemeral=True)

    @app_commands.command(name="apply", description="Подать заявку на сервер")
    async def apply(self, interaction: discord.Interaction):
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


async def setup(bot: commands.Bot):
    await bot.add_cog(ApplicationsCog(bot))