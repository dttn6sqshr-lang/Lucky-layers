import discord
from discord.ext import commands
import os, random, io
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1474038672830500966
STAFF_ROLE_ID = 1474517835261804656
LOG_CHANNEL_ID = 1475295896118755400

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

cards = {}

# -------------------------
# LOG
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

    wins = 2 if card_type != "Vanilla" else random.randint(2,4)

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
# DRAW HEART
# -------------------------
def draw_heart(draw,x,y,size,color):
    draw.ellipse((x,y,x+size//2,y+size//2), fill=color)
    draw.ellipse((x+size//2,y,x+size,y+size//2), fill=color)
    draw.polygon([(x,y+size//3),(x+size,y+size//3),(x+size//2,y+size)], fill=color)

# -------------------------
# DRAW BOW 🎀
# -------------------------
def draw_bow(draw, x, y):
    draw.polygon([(x, y), (x-8, y-6), (x-8, y+6)], fill=(255,182,193))
    draw.polygon([(x, y), (x+8, y-6), (x+8, y+6)], fill=(255,182,193))
    draw.ellipse((x-3, y-3, x+3, y+3), fill=(255,105,180))

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

    # GOLD TITLE
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()

    text = "Scratch Card"
    bbox = draw.textbbox((0,0), text, font=font)
    x = (520 - (bbox[2]-bbox[0]))//2
    y = 20

    for i, color in enumerate([(212,175,55),(230,190,70),(255,215,100)]):
        draw.text((x,y+i), text, fill=color, font=font)
    draw.text((x,y), text, fill=(120,90,40), font=font)

    # HEART SETTINGS
    size = 70
    gap_x = 105
    start_x = 45

    # TOP ROW
    for i in range(4):
        xh = start_x + i*gap_x
        yh = 90

        if not scratched[i]:
            draw_heart(draw,xh,yh,size,(200,200,200))
        else:
            draw_heart(draw,xh,yh,size,(255,60,100))
            txt = rewards[i]
            color = "gold" if is_rare(txt) else "black"
            draw.text((xh+15,yh+20),txt,fill=color,font=font)

        draw_bow(draw, xh + size//2, yh - 10)

    # BOTTOM ROW
    for i in range(4,8):
        xh = start_x + (i-4)*gap_x
        yh = 220

        if not scratched[i]:
            draw_heart(draw,xh,yh,size,(200,200,200))
        else:
            draw_heart(draw,xh,yh,size,(255,60,100))
            txt = rewards[i]
            color = "gold" if is_rare(txt) else "black"
            draw.text((xh+15,yh+20),txt,fill=color,font=font)

        draw_bow(draw, xh + size//2, yh - 10)

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
# -------------------------
class CardView(discord.ui.View):
    def __init__(self,user,rewards,ctype):
        super().__init__(timeout=None)
        for i in range(8):
            self.add_item(ScratchButton(i))

# -------------------------
# DROPDOWN
# -------------------------
class UserPicker(discord.ui.UserSelect):
    def __init__(self,staff,ctype):
        super().__init__(placeholder="Select user",min_values=1,max_values=1)
        self.staff=staff
        self.ctype=ctype

    async def callback(self,interaction):
        if interaction.user!=self.staff:
            return await interaction.response.send_message("Not yours",ephemeral=True)

        target=self.values[0]
        rewards=generate_rewards(self.ctype)

        view=CardView(target,rewards,self.ctype)
        img=create_card(self.ctype,[False]*8,rewards)
        file=discord.File(img_bytes(img),"card.png")

        msg=await interaction.channel.send(target.mention,file=file,view=view)

        cards[msg.id]={"user":target,"type":self.ctype,"rewards":rewards,"scratched":[False]*8}

        await interaction.response.send_message("Sent",ephemeral=True)

class CardTypeDropdown(discord.ui.Select):
    def __init__(self,staff):
        opts=[discord.SelectOption(label=x) for x in ["Vanilla","Sugar","Sweet","Sprinkle"]]
        super().__init__(placeholder="Choose card",options=opts)
        self.staff=staff

    async def callback(self,interaction):
        v=discord.ui.View()
        v.add_item(UserPicker(self.staff,self.values[0]))
        await interaction.response.edit_message(content="Pick user",view=v)

class GiveCardView(discord.ui.View):
    def __init__(self,staff):
        super().__init__(timeout=None)
        self.add_item(CardTypeDropdown(staff))

# -------------------------
# COMMAND
# -------------------------
@bot.tree.command(name="givecard", guild=discord.Object(id=GUILD_ID))
async def givecard(interaction):
    if not any(r.id==STAFF_ROLE_ID for r in interaction.user.roles):
        return await interaction.response.send_message("Staff only",ephemeral=True)

    await interaction.response.send_message("Choose card",view=GiveCardView(interaction.user),ephemeral=True)

# -------------------------
# READY
# -------------------------
@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print("Ready")

bot.run(TOKEN)