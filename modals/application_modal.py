import discord

from config import STAFF_CHANNEL_ID
from database import create_application, set_staff_message_id
from views.application_review_view import ApplicationReviewView


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

        application_id = await create_application(
            discord_user_id=interaction.user.id,
            discord_username=str(interaction.user),
            minecraft_nick=str(self.minecraft_nick),
            age=str(self.age),
            experience=str(self.experience),
            reason=str(self.reason),
            rules_agreement=str(self.rules_agreement),
        )

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
        embed.add_field(name="Minecraft ник", value=str(self.minecraft_nick), inline=False)
        embed.add_field(name="Возраст", value=str(self.age), inline=False)
        embed.add_field(name="Опыт игры", value=str(self.experience), inline=False)
        embed.add_field(name="Почему хочет попасть", value=str(self.reason), inline=False)
        embed.add_field(name="Согласие с правилами", value=str(self.rules_agreement), inline=False)

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