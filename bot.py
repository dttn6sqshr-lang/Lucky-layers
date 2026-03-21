import discord
from discord.ext import commands
import os

# ---------------------
# TOKEN (Railway)
# ---------------------
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("No DISCORD_TOKEN found in environment variables")

# ---------------------
# BOT SETUP
# ---------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------
# EVENTS
# ---------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ---------------------
# TEST COMMAND
# ---------------------
@bot.command()
async def ping(ctx):
    await ctx.send("pong ♡")

# ---------------------
# RUN
# ---------------------
bot.run(TOKEN)