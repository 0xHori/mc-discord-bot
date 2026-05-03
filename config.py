import os

from dotenv import load_dotenv


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
STAFF_CHANNEL_ID = os.getenv("STAFF_CHANNEL_ID")
ACCEPTED_ROLE_ID = os.getenv("ACCEPTED_ROLE_ID")
DATABASE_PATH = os.getenv("DATABASE_PATH", "applications.db")