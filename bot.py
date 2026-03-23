import discord
from discord.ext import commands
import os, random, io
from PIL import Image, ImageDraw, ImageFont

# -------------------------
# CONFIG
# -------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1474038672830500966
STAFF_ROLE_ID = 1474517835261804656
LOG_CHANNEL_ID = 1475295896118755400

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

cards = {}

# -------------------------
# AUDIT LOG
# -------------------------
async def log_action(msg):
    ch = bot.get_channel(LOG_CHANNEL_ID)
    if ch:
        await ch.send(msg)

# -------------------------
# REWARDS
# -------------------------
def generate_rewards(card_type):
    rewards = ["Nothing"] * 8

    sprinkle = [str(x) for x in range(100, 601, 50)]
    sugar = [str(x) for x in range(300, 10500, 50)]
    sweet = [str(x) for x in range(150, 1000, 50)]
    vanilla = [str(x) for x in range(100, 50001, 50)]

    if card_type in ["Sprinkle","Sugar","Sweet"]:
        wins = 2
    else:
        wins = random.randint(2,4)

    for i in random.sample(range(8), wins):
        if card_type == "Sprinkle":
            rewards[i] = random.choice(sprinkle)
        elif card_type == "Sugar":
            rewards[i] = random.choice(sugar)
        elif card_type == "Sweet":
            rewards[i] = random.choice(sweet)
        else:
            rewards[i] = random.choice(vanilla)

    return rewards

def is_rare(v):
    return v != "Nothing" and int(v) >= 1000

# -------------------------
# HEART
# -------------------------
def draw_heart(draw,x,y,size,color):
    draw.ellipse((x,y,x+size//2,y+size//2), fill=color)
    draw.ellipse((x+size//2,y,x+size,y+size//2), fill=color)
    draw.polygon([(x,y+size//3),(x+size,y+size//3),(x+size//2,y+size)], fill=color)

# -------------------------
# CARD IMAGE
# -------------------------
def create_card(card_type, scratched, rewards):
    img = Image.new("RGBA",(520,360),(255,245,230))
    draw = ImageDraw.Draw(img)

    # background
    for y in range(360):
        draw.line([(0,y),(520,y)], fill=(255,245-y//4,230+y//6))

    draw.rectangle((10,10,510,350), outline=(220,200,180), width=2)

    # title
    font = ImageFont.load_default()
    draw.text((200,20),"Scratch Card", fill="black", font=font)

    size=50
    gap_x=100
    start_x=60

    # top row
    for i in range(4):
        x = start_x + i*gap_x
        y = 90

        if not scratched[i]:
            draw_heart(draw,x,y,size,(200,200,200))
        else:
            draw_heart(draw,x,y,size,(255,60,100))
            text=rewards[i]
            if is_rare(text):
                draw.text((x+10,y+15),text,fill="gold",font=font)
            else:
                draw.text((x+10,y+15),text,fill="black",font=font)

    # bottom row
    for i in range(4,8):
        x = start_x + (i-4)*gap_x
        y = 200

        if not scratched[i]:
            draw_heart(draw,x,y,size,(200,200,200))
        else:
            draw_heart(draw,x,y,size,(255,60,100))
            text=rewards[i]
            if is_rare(text):
                draw.text((x+10,y+15),text,fill="gold",font=font)
            else:
                draw.text((x+10,y+15),text,fill="black",font=font)

    return img

def img_bytes(img):
    b=io.BytesIO()
    img.save(b,"PNG")
    b.seek(0)
    return b

# -------------------------
# BUTTON
# -------------------------
class ScratchButton(discord.ui.Button):
    def __init__(self,i):
        super().__init__(label="Scratch",style=discord.ButtonStyle.primary)
        self.i=i

    async def callback(self,interaction):
        card = cards.get(interaction.message.id)

        if interaction.user != card["user"]:
            return await interaction.response.send_message("Not yours",ephemeral=True)

        if card["scratched"][self.i]:
            return await interaction.response.send_message("Already scratched",ephemeral=True)

        card["scratched"][self.i] = True
        self.disabled = True

        img = create_card(card["type"],card["scratched"],card["rewards"])
        file = discord.File(img_bytes(img),"card.png")
        await interaction.message.edit(attachments=[file],view=self.view)

        # finish
        if all(card["scratched"]):
            for b in self.view.children:
                b.disabled=True

            rewards = card["rewards"]
            total = sum(int(r) for r in rewards if r!="Nothing")

            embed = discord.Embed(
                title="All hearts revealed…",
                description=" · ".join([r if r!="Nothing" else "nothing" for r in rewards]) + f"\n\nTotal won: {total}",
                color=0x1b1c23
            )

            await interaction.followup.send(embed=embed)
            await log_action(f"{interaction.user} finished {card['type']} → {rewards} ({total})")

# -------------------------
# VIEW