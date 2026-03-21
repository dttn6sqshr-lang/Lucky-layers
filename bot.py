import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
import io
import os
import random

TOKEN = os.getenv("DISCORD_TOKEN")
STAFF_ROLE_ID = 1474517835261804656  # your staff role

# ---------------------
# CARD CONFIG
# ---------------------
CARD_COLORS = {
    "Vanilla": ["#F8F0C6", "#FFFDD1", "#FFD3AC", "#FFE5B4"],
    "Sugar": ["#F88379", "#FFB6C1", "#DE5D83", "#FE828C"],
    "Sweet": ["#E6E6FA", "#E6E6FA", "#C8A2C8", "#DC92EF"],
    "Sprinkle": ["#3EB489", "#98FB98", "#E0BBE4", "#FEC8D8"]
}

PRIZES = {
    "Vanilla": ["Sugar Bits"],  # will generate numbers 100–50k
    "Sugar": ["BBC"],            # will generate numbers 300–10k
    "Sweet": ["Free","5%","10%","20%","25%","50%"],
    "Sprinkle": ["5 Seasonal","15 Seasonal","20 Seasonal"]
}

cards = {}  # message.id -> card info

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

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

# ---------------------
# PRIZE GENERATION
# ---------------------
def generate_rewards(card_type):
    rewards = ["Nothing"] * 8

    if card_type == "Sprinkle":
        prize_indices = random.sample(range(8), 2)
        prizes = PRIZES["Sprinkle"]
        weights = [5,4,3,1]
        for i in prize_indices:
            rewards[i] = random.choices(prizes, weights=weights, k=1)[0]

    elif card_type == "Sugar":
        prize_indices = random.sample(range(8), 2)
        sugar_options = list(range(300,10001,50))  # 300, 350, ...
        weights = [max(1, 10000 - v) for v in sugar_options]
        for i in prize_indices:
            rewards[i] = random.choices(sugar_options, weights=weights, k=1)[0]

    elif card_type == "Sweet":
        prize_indices = random.sample(range(8), 2)
        prizes = PRIZES["Sweet"]
        weights = [5,4,3,2,1,1]
        for i in prize_indices:
            rewards[i] = random.choices(prizes, weights=weights, k=1)[0]

    elif card_type == "Vanilla":
        prize_count = random.choice([2,3,4])
        prize_indices = random.sample(range(8), prize_count)
        vanilla_options = list(range(100,50001,50))  # 100,150,200,...50k
        weights = [max(1, 50000 - v) for v in vanilla_options]
        for i in prize_indices:
            rewards[i] = random.choices(vanilla_options, weights=weights, k=1)[0]

    return rewards

# ---------------------
# CREATE CARD IMAGE
# ---------------------
def create_card_image(card_type, scratched, rewards):
    width, height = 520, 320
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)

    # Gradient
    colors = [hex_to_rgb(c) for c in CARD_COLORS[card_type]]
    for y in range(height):
        pos = y / (height-1) * (len(colors)-1)
        i = int(pos)
        frac = pos - i
        if i >= len(colors)-1:
            c = colors[-1]
        else:
            c = tuple(int(colors[i][j] + (colors[i+1][j]-colors[i][j])*frac) for j in range(3))
        draw.line([(0,y),(width,y)], fill=c)

    # Hearts
    heart_coords = [
        (40,80),(160,80),(280,80),(400,80),
        (40,180),(160,180),(280,180),(400,180)
    ]

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except:
        font = ImageFont.load_default()

    heart_png = Image.open("heart.png").resize((60,60)).convert("RGBA")
    bow_png = Image.open("bow.png").resize((20,20)).convert("RGBA")

    for i,(x,y) in enumerate(heart_coords):
        heart = heart_png.copy()
        if not scratched[i]:
            overlay = Image.new("RGBA", heart.size, (255,182,193,120))
            heart.alpha_composite(overlay)
        img.alpha_composite(heart, (x,y))
        img.alpha_composite(bow_png, (x+20,y-5))

        text = "Nothing" if not scratched[i] else str(rewards[i])
        bbox = draw.textbbox((0,0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        draw.text((x+30-tw/2, y+30-th/2), text, fill="black", font=font)

    title = f"CREME COTTAGE - {card_type.upper()} CARD"
    bbox = draw.textbbox((0,0), title, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text((width/2 - tw/2, 20), title, fill="black", font=font)

    return img

# ---------------------
# BUTTONS & VIEWS
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

        if all(card["scratched"]):
            await interaction.followup.send(f"🎉 You’ve completed your {card['type']} card!", ephemeral=True)

class ScratchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i in range(8):
            self.add_item(ScratchButton(i))

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
        rewards = generate_rewards(card_type)
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
# COMMAND
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

bot.run(TOKEN)