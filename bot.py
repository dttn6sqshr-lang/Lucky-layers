import discord
from discord.ext import commands
from discord import app_commands
import os
import io
from PIL import Image, ImageDraw, ImageFont
import random

# ---------------------
# CONFIG
# ---------------------
TOKEN = os.getenv("DISCORD_TOKEN")
STAFF_ROLE_ID = 1474517835261804656

# CARD COLORS (per type)
CARD_COLORS = {
    "Vanilla": ["#F8F0C6", "#FFFDD1", "#FFD3AC", "#FFE5B4"],
    "Sugar": ["#F88379", "#FFB6C1", "#DE5D83", "#FE828C"],
    "Sweet": ["#E6E6FA", "#E6E6FA", "#C8A2C8", "#DC92EF"],
    "Sprinkle": ["#3EB489", "#98FB98", "#E0BBE4", "#FEC8D8"]
}

# ---------------------
# BOT SETUP
# ---------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------
# DATA STORAGE
# ---------------------
cards = {}  # message.id : card info

# ---------------------
# HELPERS
# ---------------------
def is_staff(member: discord.Member):
    return any(role.id == STAFF_ROLE_ID for role in member.roles)

def img_to_bytes(img):
    b = io.BytesIO()
    img.save(b, format="PNG")
    b.seek(0)
    return b

def create_card_image(card_type, scratched):
    """Generate card image with hearts and 'Nothing' for un-scratched panels."""
    width, height = 520, 320
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)
    
    # Gradient background
    colors = CARD_COLORS.get(card_type, ["#FFFFFF"])
    for y in range(height):
        color_index = int(y / height * (len(colors)-1))
        draw.line([(0,y),(width,y)], fill=colors[color_index])
    
    # Draw 8 hearts
    heart_coords = [
        (40, 80),(160, 80),(280, 80),(400, 80),
        (40, 180),(160, 180),(280, 180),(400, 180)
    ]
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except:
        font = ImageFont.load_default()
    
    for i, (x,y) in enumerate(heart_coords):
        # Heart panel background
        overlay_color = (255,255,255,200) if scratched[i] else (0,0,0,180)
        draw.rectangle([x,y,x+100,y+90], fill=overlay_color, outline=(0,0,0))
        # Draw text
        text = "Nothing" if not scratched[i] else "💖"
        tw, th = draw.textsize(text, font=font)
        draw.text((x+(100-tw)/2, y+(90-th)/2), text, fill="black", font=font)
    
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
        # regenerate image
        img = create_card_image(card["type"], card["scratched"])
        file = discord.File(img_to_bytes(img), filename="card.png")
        
        # deactivate button
        self.disabled = True
        await interaction.response.edit_message(attachments=[file], view=self.view)
        
        # check if card complete
        if all(card["scratched"]):
            await interaction.followup.send(f"🎉 {interaction.user.mention}, your {card['type']} card is complete!")

class ScratchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i in range(8):
            self.add_item(ScratchButton(i))

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
        super().__init__(placeholder="🎀 Choose a card type...", min_values=1, max_values=1, options=options)
        self.target = target
    
    async def callback(self, interaction: discord.Interaction):
        card_type = self.values[0]
        # create card data
        scratched = [False]*8
        img = create_card_image(card_type, scratched)
        file = discord.File(img_to_bytes(img), filename="card.png")
        
        view = ScratchView()
        await interaction.response.send_message(
            f"🎀 {self.target.mention} received a **{card_type} card**!",
            file=file,
            view=view
        )
        # store card
        msg = await interaction.original_response()
        cards[msg.id] = {"user": self.target, "type": card_type, "scratched": scratched}

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