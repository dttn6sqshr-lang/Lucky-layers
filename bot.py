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
def generate_rewards(card_type):
    rewards = ["Nothing"] * 8

    # pools
    sprinkle_pool = [str(x) for x in range(100, 601, 50)]
    sugar_pool = [str(x) for x in range(300, 10500, 50)]
    sweet_pool = [str(x) for x in range(150, 1000, 50)]
    vanilla_pool = [str(x) for x in range(100, 50001, 50)]

    # determine win count
    if card_type in ["Sprinkle", "Sugar", "Sweet"]:
        win_count = 2
    elif card_type == "Vanilla":
        win_count = random.randint(2,4)
    else:
        win_count = 2

    positions = random.sample(range(8), win_count)

    for pos in positions:
        if card_type == "Sprinkle":
            rewards[pos] = random.choice(sprinkle_pool)
        elif card_type == "Sugar":
            rewards[pos] = random.choices(
                sugar_pool,
                weights=[max(1, 10000 - int(x)) for x in sugar_pool]
            )[0]
        elif card_type == "Sweet":
            rewards[pos] = random.choice(sweet_pool)
        elif card_type == "Vanilla":
            rewards[pos] = random.choices(
                vanilla_pool,
                weights=[max(1, 50000 - int(x)) for x in vanilla_pool]
            )[0]

    return rewards

def is_rare(v):
    return v != "Nothing" and int(v) >= 1000

# -------------------------
# HEART DRAWING
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

    # gradient background
    for y in range(360):
        r=255
        g=int(245-y*0.1)
        b=int(230+y*0.2)
        draw.line([(0,y),(520,y)], fill=(r,g,b))

    # border
    draw.rectangle((10,10,510,350), outline=(220,200,180), width=2)

    # envelope flap
    draw.polygon([(100,10),(260,90),(420,10)], fill=(255,230,210))

    # wax seal
    cx,cy=260,80
    draw.ellipse((cx-20,cy-20,cx+20,cy+20), fill=(200,60,90))
    for g in range(3):
        draw.ellipse((cx-22-g,cy-22-g,cx+22+g,cy+22+g), outline=(255,215,0))

    # TITLE
    font_title = ImageFont.load_default()
    draw.text((200,100),"Scratch Card", fill="black", font=font_title)

    font = ImageFont.load_default()

    # hearts layout (spaced out)
    size=50
    start_x=50
    start_y=140
    gap_x=110
    gap_y=110

    for i in range(8):
        r=i//4
        c=i%4
        x=start_x + c*gap_x
        y=start_y + r*gap_y

        if not scratched[i]:
            draw_heart(draw,x,y,size,(200,200,200))  # gray cover
        else:
            draw_heart(draw,x,y,size,(255,60,100))
            text=rewards[i]
            if is_rare(text):
                for glow in range(3):
                    draw.text((x+10-glow,y+15),text,fill="gold",font=font)
            draw.text((x+10,y+15),text,fill="black",font=font)

    # subtle sparkles
    for _ in range(8):
        sx=random.randint(0,520)
        sy=random.randint(0,360)
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
        card = cards.get(interaction.message.id)
        if interaction.user != card["user"]:
            return await interaction.response.send_message("Not yours.",ephemeral=True)

        if card["scratched"][self.i]:
            return await interaction.response.send_message("Already scratched.",ephemeral=True)

        card["scratched"][self.i] = True
        self.disabled = True

        img = create_card(card["type"],card["scratched"],card["rewards"])
        file = discord.File(img_bytes(img),"card.png")
        await interaction.message.edit(attachments=[file],view=self.view)

        if all(card["scratched"]):
            for btn in self.view.children:
                btn.disabled = True

            rewards_list = card["rewards"]
            total = sum(int(r) for r in rewards_list if r != "Nothing")

            embed = discord.Embed(
                title="All hearts revealed…",
                description=" · ".join([r if r != "Nothing" else "nothing" for r in rewards_list])
                            + f"\n\nTotal won: {total}",
                color=0x1b1c23
            )

            if any(int(r) >= 10000 for r in rewards_list if r != "Nothing"):
                embed.add_field(name="Jackpot!", value="A rare reward has been pulled", inline=False)

            await interaction.followup.send(embed=embed)
            await log_action(f"{interaction.user} finished {card['type']} → {rewards_list} (Total: {total})")

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
        if interaction.user != self.staff:
            return await interaction.response.send_message("Not yours.",ephemeral=True)

        target=self.values[0]
        rewards=generate_rewards(self.ctype)
        view=CardView(target,rewards,self.ctype)
        img=create_card(self.ctype,[False]*8,rewards)
        file=discord.File(img_bytes(img),"card.png")

        msg=await interaction.channel.send(
            f"A delicate letter arrives… {target.mention}",
            file=file,
            view=view
        )

        cards[msg.id]={"user":target,"type":self.ctype,"rewards":rewards,"scratched":[False]*8}
        get_user(interaction.user.id)["given"]+=1
        await interaction.response.send_message("Sent!",ephemeral=True)
        await log_action(f"{interaction.user} gave {self.ctype} to {target}")

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
    print("Bot ready!")

bot.run(TOKEN)