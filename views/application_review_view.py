import discord

from config import ACCEPTED_ROLE_ID
from database import (
    get_application_status,
    update_application_status,
    create_moderation_decision,
    get_application_user_id,
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
            await self.assign_accepted_role(interaction)

        await self.notify_applicant(interaction, decision)
        await self.update_review_message(interaction, decision)

        status_text = "Принята" if decision == "accepted" else "Отклонена"

        await interaction.followup.send(
            f"Заявка #{self.application_id} отмечена как: {status_text}",
            ephemeral=True,
        )

    async def assign_accepted_role(self, interaction: discord.Interaction):
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

        user_id = await get_application_user_id(self.application_id)
        member = interaction.guild.get_member(user_id)

        if member is None:
            try:
                member = await interaction.guild.fetch_member(user_id)
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


    async def notify_applicant(
        self,
        interaction: discord.Interaction,
        decision: str,
    ):
        user_id = await get_application_user_id(self.application_id)

        try:
            user = await interaction.client.fetch_user(user_id)
        except discord.NotFound:
            await interaction.followup.send(
                "Не удалось найти пользователя для отправки уведомления.",
                ephemeral=True,
            )
            return

        if decision == "accepted":
            message = (
                f"Твоя заявка #{self.application_id} на сервер была принята. "
                "Добро пожаловать!"
            )
        else:
            message = (
                f"Твоя заявка #{self.application_id} на сервер была отклонена."
            )

        try:
            await user.send(message)
        except discord.Forbidden:
            await interaction.followup.send(
                "Заявка обработана, но не удалось отправить пользователю ЛС.",
                ephemeral=True,
            )


    async def update_review_message(
        self,
        interaction: discord.Interaction,
        decision: str,
    ):
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