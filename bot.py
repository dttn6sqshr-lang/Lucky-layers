import discord
from discord.ext import commands
from discord import app_commands
import os

# ---------------------
# CONFIG
# ---------------------
TOKEN = os.getenv("DISCORD_TOKEN")

# your staff role ID
STAFF_ROLE_ID = 1474517835261804656

# ---------------------
# BOT SETUP
# ---------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------
# STAFF CHECK
# ---------------------
def is_staff(member: discord.Member):
    return any(role.id == STAFF_ROLE_ID for role in member.roles)

# ---------------------
# DROPDOWN
# ---------------------
class CardDropdown(discord.ui.Select):
    def __init__(self, target: discord.Member):
        options = [
            discord.SelectOption(label="Vanilla", emoji="🍦"),
            discord.SelectOption(label="Sugar", emoji="🍬"),
            discord.SelectOption(label="Sweet", emoji="🍰"),
            discord.SelectOption(label="Sprinkle", emoji="🍩"),
        ]
        super().__init__(
            placeholder="🎀 Choose a card type...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.target = target

    async def callback(self, interaction: discord.Interaction):
        card_type = self.values