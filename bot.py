import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
import io
import os
import random

# ---------------------
# CONFIG
# ---------------------
TOKEN = os.getenv("DISCORD_TOKEN")
STAFF_ROLE_ID = 1474517835261804656

# CARD COLORS
CARD_COLORS = {
    "Vanilla": ["#F8F0C6", "#FFFDD1", "#FFD3AC", "#FFE5B4"],
    "Sugar": ["#F88379", "#FFB6C1", "#DE5D83", "#FE828C"],
    "Sweet": ["#E6E6FA", "#E6E6FA", "#C8A2C8", "#DC92EF"],
    "Sprinkle": ["#3EB489", "#98FB98", "#E0BBE4", "#FEC8D8"]
}

# PRIZE POOLS
PRIZES = {
    "Vanilla": ["100","200","500","1000","5000"],
    "Sugar": ["300","400","500","600","700","800"],
    "Sweet": ["Free","5%","10%","20%","25%","50%"],
    "Sprinkle": ["5 Seasonal","15 Seasonal","20 Seasonal"]
}

# ---------------------
# BOT SETUP
# ---------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

cards = {}  # message.id : card info

# ---------------------
# HELPERS
# ---------------------
def is_staff(member):
    return any(r.id == STAFF_ROLE_ID for r in member.roles)

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def img_to_bytes(img):
    b = io.BytesIO()
    img.save(b, format="PNG")
    b.seek(0)
    return b

def create_card_image(card_type, scratched, rewards):
    """Draw gradient background, hearts, bows, and prizes"""
    width, height = 520, 320
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)

    # Gradient background
    colors = [hex_to_rgb(c) for c in CARD_COLORS.get(card_type, ["#FFF"])]
    for y in range(height):
        pos = y / (height-1) * (len(colors)-1)
        i = int(pos)
        frac = pos - i
        if i >= len(colors)-1:
            c = colors[-1]
        else:
            c = tuple(int(colors[i][j] + (colors[i+1][j]-colors[i][j])*frac) for j in range(3))
        draw.line([(0,y),(width,y)], fill=c)

    # Heart coordinates
    heart_coords = [
        (40, 80),(160, 80),(280, 80),(400, 80),
        (40, 180),(160, 180),(280, 180),(400, 180)
    ]

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        bow_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()
        bow_font = ImageFont.load_default()

    for i, (x, y) in enumerate(heart_coords):
        # Heart shape using polygon
        heart = [
            (x+50, y+0), (x+90, y+30), (x+70, y+80), (x+30, y+80), (x+10, y+30)
        ]
        fill_color = (255,182,193,150) if not scratched[i] else (255,105,180,200)
        draw.polygon(heart, fill=fill_color, outline=(0,0,0))

        # Bow on heart corner
        draw.text((x+35, y-5), "🎀", font=bow_font, fill="black")

        # Prize text
        text = "Nothing" if not scratched[i] else rewards[i]
        bbox = draw.textbbox((0,0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        draw.text((x+50-tw/2, y+40-th/2), text, fill="black", font=font)

    # Title
    title = f"CREME COTTAGE - {card_type.upper()} CARD"
    bbox = draw.textbbox((0,0), title, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text((width/2 - tw/2, 20), title, fill="black", font=font)

    return img

# ---------------------
# BUTTONS
# ---------------------
class ScratchButton(discord.ui.Button):
    def __init__(self, index):
        super().__init__(label="Scratch", style=discord.ButtonStyle.secondary)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        card = cards.get(interaction.message.id)
        if interaction.user.id != card["user"].id:
            return await interaction.response.send_message("This isn't your card.", ephemeral=True)

        if card["scratched"][self.index]:
            return await interaction.response.send_message("Already scratched.", ephemeral=True)

        card["scratched"][self.index] = True
        img = create_card_image(card["type"], card["scratched"], card["rewards"])
        file = discord.File(img_to_bytes(img), filename="card.png")

        self.disabled = True
        await interaction.response.edit_message(attachments=[file], view=self.view)

        # Ephemeral complete message
        if all(card["scratched"]):
            await interaction.followup.send(f"🎉 You’ve completed your {card['type']} card!", ephemeral=True)

class ScratchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i in range(8):
            self.add_item(ScratchButton(i))

# ---------------------
# DROPDOWN
# ---------------------
class CardDropdown(discord.ui.Select):
    def __init__(self, target):
        options = [
            discord.SelectOption(label="Vanilla", emoji="🍦"),
            discord.SelectOption(label="Sugar", emoji="🍬"),
            discord.SelectOption(label="Sweet", emoji="🍰"),
            discord.SelectOption(label="Sprinkle", emoji="🍩")
        ]
        super().__init__(placeholder="🎀 Choose a card type...", min_values=1, max_values=1, options=options)
        self.target = target

    async def callback(self, interaction: discord.Interaction):
        card_type = self.values[0]
        rewards = random.choices(PRIZES[card_type], k=8)
        scratched = [False]*8
        img = create_card_image(card_type, scratched, rewards)
        file = discord.File(img_to_bytes(img), filename="card.png")
        view = ScratchView()
        await interaction.response.send_message(
            f"🎀 {self.target.mention} received a **{card_type} card**!",
            file=file,
            view=view
        )
        msg = await interaction.original_response()
        cards[msg.id] = {"user": self.target, "type": card_type, "scratched": scratched, "rewards": rewards}

class CardView(discord.ui.View):
    def __init__(self, target):
        super().__init__()
        self.add_item(CardDropdown(target))

# ---------------------
# SLASH COMMAND
# ---------------------
@bot.tree.command(name="give_card", description="Give a scratch card")
@app_commands.describe(user="User to receive the card")
async def give_card(interaction: discord.Interaction, user: discord.Member):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ You can't give cards.", ephemeral=True)
        return
    view = CardView(user)
    await interaction.response.send_message(f"{interaction.user.mention}, choose a card for {user.mention}:", view=view)

# ---------------------
# READY
# ---------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

# ---------------------
# RUN
# ---------------------
bot.run(TOKEN)