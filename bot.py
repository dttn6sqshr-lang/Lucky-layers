import discord
from discord.ext import commands
import json
import os
import random
import io
from PIL import Image, ImageDraw, ImageFont

# ---------------------
# CONFIG
# ---------------------
TOKEN = "YOUR_BOT_TOKEN_HERE"
LOG_CHANNEL = "logs"
DATA_FILE = "scratch_data.json"

CARD_WIDTH, CARD_HEIGHT = 520, 320
BOX_WIDTH, BOX_HEIGHT = 95, 95
BOX_COORDS = [
    (20,100),(140,100),(260,100),(380,100),
    (20,200),(140,200),(260,200),(380,200)
]

CARD_TYPES = {
    "vanilla": ["#F8F0C6","#FFFDD1","#FFD3AC","#FFE5B4"],
    "sugar": ["#F88379","#FFB6C1","#DE5D83","#FE828C"],
    "sweet": ["#E6E6FA","#E6E6FA","#C8A2C8","#DC92EF"],
    "sprinkle": ["#3EB489","#98FB98","#E0BBE4","#FEC8D8"]
}

# ---------------------
# BOT SETUP
# ---------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------
# DATA
# ---------------------
if os.path.exists(DATA_FILE):
    with open(DATA_FILE,"r") as f:
        data = json.load(f)
else:
    data = {"cards":{}, "users":{}, "card_counter":0, "givers":{}}

def save_data():
    with open(DATA_FILE,"w") as f:
        json.dump(data,f,indent=4)

# ---------------------
# HELPERS
# ---------------------
def get_log_channel(guild):
    return discord.utils.get(guild.text_channels,name=LOG_CHANNEL)

def img_to_bytes(img):
    b = io.BytesIO()
    img.save(b,format="PNG")
    b.seek(0)
    return b

def draw_text_centered(draw,x,y,w,h,text,font_size=36):
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0,0),text,font=font)
    tw = bbox[2]-bbox[0]
    th = bbox[3]-bbox[1]
    draw.text((x+(w-tw)/2, y+(h-th)/2), text, fill="black", font=font)

def create_card_image(card_type,rewards,scratched):
    colors = CARD_TYPES[card_type]
    img = Image.new("RGBA",(CARD_WIDTH,CARD_HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(CARD_HEIGHT):
        cidx = y*len(colors)//CARD_HEIGHT
        draw.line([(0,y),(CARD_WIDTH,y)],fill=colors[cidx])
    draw_text_centered(draw,0,20,CARD_WIDTH,50,f"CREME COTTAGE {card_type.upper()} CARD",36)
    for i,(x,y) in enumerate(BOX_COORDS):
        draw.rounded_rectangle([x,y,x+BOX_WIDTH,y+BOX_HEIGHT],radius=18,fill=(255,255,255,230))
        if scratched[i]:
            draw_text_centered(draw,x,y,BOX_WIDTH,BOX_HEIGHT,str(rewards[i]),font_size=36)
        else:
            overlay = Image.new("RGBA",(BOX_WIDTH,BOX_HEIGHT),(0,0,0,180))
            img.alpha_composite(overlay,(x,y))
    return img

# ---------------------
# READY
# ---------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot ready as {bot.user}")

bot.run(TOKEN)