import discord
from discord.ext import commands
import os, random, io, asyncio
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
data = {}

# -------------------------
# USER DATA
# -------------------------
def get_user(uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {"sugar":0, "opened":0, "given":0, "badges":[]}
    return data[uid]

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
def generate_rewards():
    pool = [
        ("Nothing", 50),
        ("100", 25),
        ("250", 15),
        ("500", 7),
        ("1000", 3)
    ]
    rewards = []
    for _ in range(8):
        rewards.append(random.choices(
            [p[0] for p in pool],
            weights=[p[1] for p in pool]
        )[0])
    return rewards

def is_rare(v):
    return v not in ["Nothing","100"]

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
    img = Image.new("RGBA",(520,320),(255,245,230))
    draw = ImageDraw.Draw(img)

    # gradient
    for y in range(320):
        r=255
        g=int(245-y*0.1)
        b=int(230+y*0.2)
        draw.line([(0,y),(520,y)], fill=(r,g,b))

    # border
    draw.rectangle((10,10,510,310), outline=(220,200,180), width=2)

    # envelope flap
    draw.polygon([(100,10),(260,90),(420,10)], fill=(255,230,210))

    # wax seal
    cx,cy=260,80
    draw.ellipse((cx-20,cy-20,cx+20,cy+20), fill=(200,60,90))
    for g in range(3):
        draw.ellipse((cx-22-g,cy-22-g,cx+22+g,cy+22+g), outline=(255,215,0))

    font = ImageFont.load_default()

    # hearts
    size=50
    start_x=60
    start_y=120
    gap_x=90
    gap_y=90

    for i in range(8):
        r=i//4
        c=i%4
        x=start_x + c*gap_x
        y=start_y + r*gap_y

        if not scratched[i]:
            draw_heart(draw,x,y,size,(200,200,200))
            draw.text((x+15,y+15),"?",fill="black",font=font)
        else:
            draw_heart(draw,x,y,size,(255,60,100))
            text=rewards[i]

            if is_rare(text):
                for glow in range(3):
                    draw.text((x+10-glow,y+15),text,fill="gold",font=font)

            draw.text((x+10,y+15),text,fill="black",font=font)

    # sparkles
    for _ in range(8):
        sx=random.randint(0,520)
        sy=random.randint(0,320)
        draw.text((sx,sy),"✨",fill=(255,215,0),font=font)

    return img

def img_bytes(img):
    b=io.BytesIO()
    img.save(b,"PNG")
    b.seek(0)
    return b

# -------------------------
# SCRATCH BUTTON
# -------------------------
class ScratchButton(discord.ui.Button):
    def __init__(self,i):
        super().__init__(label="Scratch!",style=discord.ButtonStyle.primary)
        self.i=i

    async def callback(self,interaction):
        card=cards.get(interaction.message.id)

        if interaction.user!=card["user"]:
            await interaction.response.send_message("Not yours.",ephemeral=True)
            await log_action(f"⚠️ {interaction.user} tried чуж card")
            return

        if card["scratched"][self.i]:
            return await interaction.response.send_message("Already.",ephemeral=True)

        card["scratched"][self.i]=True

        # animation
        for _ in range(2):
            img=create_card(card["type"],card["scratched"],card["rewards"])
            file=discord.File(img_bytes(img),"card.png")
            await interaction.message.edit(attachments=[file],view=self.view)
            await asyncio.sleep(0.2)

        self.disabled=True

        reward=card["rewards"][self.i]
        user=get_user(interaction.user.id)

        if reward!="Nothing":
            user["sugar"]+=int(reward)

        user["opened"]+=1

        await log_action(f"✨ {interaction.user} scratched {self.i+1} → {reward}")

        if all(card["scratched"]):
            for c in self.view.children:
                c.disabled=True
            await interaction.followup.send("🎉 Card complete!",ephemeral=True)

# -------------------------
# VIEW
# -------------------------
class CardView(discord.ui.View):
    def __init__(self,user,rewards,ctype):
        super().__init__(timeout=None)
        for i in range(8):
            self.add_item(ScratchButton(i))

# -------------------------
# DROPDOWN FLOW
# -------------------------
class UserPicker(discord.ui.UserSelect):
    def __init__(self,staff,ctype):
        super().__init__(placeholder="Select user",min_values=1,max_values=1)
        self.staff=staff
        self.ctype=ctype

    async def callback(self,interaction):
        if interaction.user!=self.staff:
            return await interaction.response.send_message("Not yours.",ephemeral=True)

        target=self.values[0]
        rewards=generate_rewards()

        view=CardView(target,rewards,self.ctype)
        img=create_card(self.ctype,[False]*8,rewards)
        file=discord.File(img_bytes(img),"card.png")

        msg=await interaction.channel.send(
            f"✦🌸✧  A delicate letter arrives…\n💌 {target.mention}",
            file=file,
            view=view
        )

        cards[msg.id]={"user":target,"type":self.ctype,"rewards":rewards,"scratched":[False]*8}

        get_user(interaction.user.id)["given"]+=1

        await interaction.response.send_message("Sent!",ephemeral=True)
        await log_action(f"💌 {interaction.user} gave {self.ctype} to {target}")

class CardTypeDropdown(discord.ui.Select):
    def __init__(self,staff):
        opts=[discord.SelectOption(label=x) for x in ["Vanilla","Sugar","Sweet","Sprinkle"]]
        super().__init__(placeholder="Choose card",options=opts)
        self.staff=staff

    async def callback(self,interaction):
        v=discord.ui.View()
        v.add_item(UserPicker(self.staff,self.values[0]))
        await interaction.response.edit_message(content="Pick recipient:",view=v)

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
        return await interaction.response.send_message("Staff only.",ephemeral=True)

    await interaction.response.send_message("Choose card:",view=GiveCardView(interaction.user),ephemeral=True)

# -------------------------
# READY
# -------------------------
@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print("Ready")

bot.run(TOKEN)