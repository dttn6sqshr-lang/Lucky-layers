import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
import random, json, io, os

# ---------------------
# CONFIG
# ---------------------
TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "scratch_data.json"
LOG_CHANNEL = "logs"

STAFF_ROLE_IDS = [123456789012345678]  # ✨ PUT YOUR STAFF ROLE ID HERE

CARD_WIDTH, CARD_HEIGHT = 520, 320

CARD_TYPES = {
    "vanilla": ["#F8F0C6","#FFFDD1","#FFD3AC","#FFE5B4"],
    "sugar": ["#F88379","#FFB6C1","#DE5D83","#FE828C"],
    "sweet": ["#E6E6FA","#C8A2C8","#DC92EF"],
    "sprinkle": ["#3EB489","#98FB98","#E0BBE4","#FEC8D8"]
}

# ---------------------
# BOT
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
    data = {"cards":{}, "givers":{}, "users":{}}

def save():
    with open(DATA_FILE,"w") as f:
        json.dump(data,f,indent=4)

# ---------------------
# HELPERS
# ---------------------
def is_staff(member):
    return any(role.id in STAFF_ROLE_IDS for role in member.roles)

def get_log(guild):
    return discord.utils.get(guild.text_channels, name=LOG_CHANNEL)

def img_bytes(img):
    b = io.BytesIO()
    img.save(b,format="PNG")
    b.seek(0)
    return b

def heart(draw, x, y, size, color):
    w = size
    draw.polygon([
        (x+w*0.5, y+w),
        (x, y+w*0.3),
        (x+w*0.25, y),
        (x+w*0.5, y+w*0.3),
        (x+w*0.75, y),
        (x+w, y+w*0.3)
    ], fill=color)

def make_card(rewards, scratched, ctype):
    img = Image.new("RGBA",(CARD_WIDTH,CARD_HEIGHT))
    draw = ImageDraw.Draw(img)

    colors = CARD_TYPES[ctype]

    # gradient
    for y in range(CARD_HEIGHT):
        idx = int((y/CARD_HEIGHT)*(len(colors)-1))
        draw.line([(0,y),(CARD_WIDTH,y)],fill=colors[idx])

    coords = [(50,100),(180,100),(310,100),(440,100),
              (50,200),(180,200),(310,200),(440,200)]

    for i,(x,y) in enumerate(coords):
        heart(draw,x,y,60,"#FFF0F5")  # soft pink tint

        if scratched[i]:
            text = rewards[i]
        else:
            text = "♡"  # FIXED (no more ⍰)

        draw.text((x+18,y+20), str(text), fill="black")

        # tiny bow
        draw.text((x+40,y-5),"🎀",fill="pink")

    return img

def gen_rewards(ctype):
    rewards = ["Nothing"]*8

    if ctype == "vanilla":
        pool = [100,200,500,1000,2000]
    elif ctype == "sugar":
        pool = [50,100,150,200]
    elif ctype == "sweet":
        pool = ["5%","10%","20%"]
    else:
        pool = ["Seasonal","Rare","Ultra"]

    for i in random.sample(range(8),3):
        rewards[i] = str(random.choice(pool))

    return rewards

# ---------------------
# SCRATCH VIEW
# ---------------------
class ScratchBtn(discord.ui.Button):
    def __init__(self,i):
        super().__init__(label="Scratch",style=discord.ButtonStyle.secondary)
        self.i = i

    async def callback(self,interaction:discord.Interaction):
        card = data["cards"].get(str(interaction.message.id))
        if not card: return

        if interaction.user.id != card["user"]:
            return await interaction.response.send_message("Not your card!",ephemeral=True)

        if card["scratched"][self.i]:
            return await interaction.response.send_message("Already scratched!",ephemeral=True)

        card["scratched"][self.i] = True
        self.disabled = True

        img = make_card(card["rewards"],card["scratched"],card["type"])
        file = discord.File(img_bytes(img),"card.png")

        await interaction.response.edit_message(attachments=[file], view=self.view)

        reward = card["rewards"][self.i]

        log = get_log(interaction.guild)
        if log:
            msg = f"{interaction.user.display_name} scratched → `{reward}`"
            if reward not in ["Nothing","50","100"]:
                msg += " ✨ RARE!"
            await log.send(msg)

        # completion
        if all(card["scratched"]):
            await interaction.followup.send("🎀 card complete! all layers revealed ♡")

        save()

class ScratchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i in range(8):
            self.add_item(ScratchBtn(i))

# ---------------------
# GIVE CARD (STAFF ONLY)
# ---------------------
class CardDropdown(discord.ui.Select):
    def __init__(self,user):
        options = [discord.SelectOption(label=k.title()) for k in CARD_TYPES]
        super().__init__(placeholder="Select card type", options=options)
        self.user = user

    async def callback(self,interaction:discord.Interaction):
        ctype = self.values[0].lower()

        rewards = gen_rewards(ctype)
        scratched = [False]*8

        img = make_card(rewards,scratched,ctype)
        file = discord.File(img_bytes(img),"card.png")

        view = ScratchView()

        await interaction.response.send_message(
            f"{self.user.mention} received a {ctype} card ♡",
            file=file,
            view=view
        )

        msg = await interaction.original_response()

        data["cards"][str(msg.id)] = {
            "user": self.user.id,
            "rewards": rewards,
            "scratched": scratched,
            "type": ctype
        }

        giver = interaction.user.id
        data["givers"][str(giver)] = data["givers"].get(str(giver),0)+1

        save()

class CardView(discord.ui.View):
    def __init__(self,user):
        super().__init__()
        self.add_item(CardDropdown(user))

@bot.tree.command(name="give_card")
async def give_card(interaction: discord.Interaction, user: discord.Member):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("Staff only!", ephemeral=True)

    await interaction.response.send_message(
        "Select a card type:",
        view=CardView(user),
        ephemeral=True
    )

# ---------------------
# LEADERBOARD
# ---------------------
@bot.tree.command(name="giver_leaderboard")
async def giver_lb(interaction:discord.Interaction):
    sorted_users = sorted(data["givers"].items(), key=lambda