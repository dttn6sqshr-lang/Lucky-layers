import discord
from discord.ext import commands
import random, json, io, os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# -------------------------
# CONFIG
# -------------------------
TOKEN = os.getenv("DISCORD_TOKEN")

STAFF_ROLE_ID = 1474517835261804656
AUDIT_CHANNEL_ID = 1475295896118755400
DATA_FILE = "data.json"

CARD_TYPES = ["Vanilla", "Sugar", "Sweet", "Sprinkle"]

# -------------------------
# BOT SETUP
# -------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # important

bot = commands.Bot(command_prefix="!", intents=intents)

data = {}
cards = {}

# -------------------------
# LOAD/SAVE
# -------------------------
def load_data():
    global data
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except:
        data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_user(uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {"sugar_bits": 0, "cards_opened": 0}
    return data[uid]

# -------------------------
# AUDIT LOG
# -------------------------
async def log_audit(text):
    channel = bot.get_channel(AUDIT_CHANNEL_ID)
    if channel:
        await channel.send(f"📝 {text}")

# -------------------------
# CARD SYSTEM
# -------------------------
def generate_rewards(card_type):
    rewards = []
    for _ in range(4):
        rewards.append(random.choice(["Nothing", "100", "250", "500", "1000"]))
    return rewards

def create_card(scratched, rewards):
    img = Image.new("RGBA", (520, 320), (255, 182, 193))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    for i in range(4):
        x = 80 + i * 110
        y = 120

        # ❤️ actual heart-ish shape
        draw.polygon([
            (x, y+20), (x+30, y-10), (x+60, y+20),
            (x+45, y+60), (x+15, y+60)
        ], fill="red")

        if scratched[i]:
            text = rewards[i]
            draw.text((x+10, y+20), text, fill="black", font=font)

    return img

def img_bytes(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    b.seek(0)
    return b

# -------------------------
# SCRATCH VIEW
# -------------------------
class ScratchButton(discord.ui.Button):
    def __init__(self, index):
        super().__init__(label=f"Heart {index+1}", style=discord.ButtonStyle.primary)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        card = cards.get(interaction.message.id)

        if interaction.user != card["user"]:
            return await interaction.response.send_message("Not your card.", ephemeral=True)

        if card["scratched"][self.index]:
            return await interaction.response.send_message("Already scratched.", ephemeral=True)

        card["scratched"][self.index] = True

        img = create_card(card["scratched"], card["rewards"])
        file = discord.File(img_bytes(img), "card.png")

        await interaction.response.edit_message(attachments=[file], view=self.view)

        reward = card["rewards"][self.index]
        if reward != "Nothing":
            user = get_user(interaction.user.id)
            user["sugar_bits"] += int(reward)
            user["cards_opened"] += 1
            save_data()

        await log_audit(f"{interaction.user} scratched → {reward}")

class CardView(discord.ui.View):
    def __init__(self, user, rewards):
        super().__init__(timeout=None)
        self.user = user
        self.rewards = rewards

        for i in range(4):
            self.add_item(ScratchButton(i))

# -------------------------
# USER SELECT (🔥 FIXED)
# -------------------------
class UserPicker(discord.ui.UserSelect):
    def __init__(self, staff_user, card_type):
        super().__init__(placeholder="🎀 Select recipient", min_values=1, max_values=1)
        self.staff_user = staff_user
        self.card_type = card_type

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.staff_user:
            return await interaction.response.send_message("Not your menu.", ephemeral=True)

        target = self.values[0]

        rewards = generate_rewards(self.card_type)
        view = CardView(target, rewards)

        img = create_card([False]*4, rewards)
        file = discord.File(img_bytes(img), "card.png")

        msg = await interaction.channel.send(
            f"{target.mention}, you got a {self.card_type} card!",
            file=file,
            view=view
        )

        cards[msg.id] = {
            "user": target,
            "rewards": rewards,
            "scratched": [False]*4
        }

        await interaction.response.send_message("✅ Card sent!", ephemeral=True)

# -------------------------
# CARD TYPE DROPDOWN
# -------------------------
class CardTypeDropdown(discord.ui.Select):
    def __init__(self, staff_user):
        options = [discord.SelectOption(label=ct) for ct in CARD_TYPES]
        super().__init__(placeholder="🎀 Choose card type", options=options)
        self.staff_user = staff_user

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.staff_user:
            return await interaction.response.send_message("Not yours.", ephemeral=True)

        card_type = self.values[0]

        view = discord.ui.View()
        view.add_item(UserPicker(self.staff_user, card_type))

        await interaction.response.edit_message(
            content=f"Select recipient for {card_type}",
            view=view
        )

class GiveCardView(discord.ui.View):
    def __init__(self, staff_user):
        super().__init__(timeout=None)
        self.add_item(CardTypeDropdown(staff_user))

# -------------------------
# COMMAND
# -------------------------
@bot.tree.command(name="givecard", description="Give a scratch card")
async def givecard(interaction: discord.Interaction):
    if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message("Staff only.", ephemeral=True)

    await interaction.response.send_message(
        "🎀 Choose a card type:",
        view=GiveCardView(interaction.user),
        ephemeral=True
    )

# -------------------------
# READY (🔥 RESET COMMANDS)
# -------------------------
@bot.event
async def on_ready():
    load_data()

    try:
        bot.tree.clear_commands(guild=None)  # remove old global
        await bot.tree.sync()
    except Exception as e:
        print(e)

    print(f"✅ {bot.user} is online!")

# -------------------------
bot.run(TOKEN)