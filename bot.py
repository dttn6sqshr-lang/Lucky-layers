import discord
from discord.ext import commands
import random, json, io, os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# -------------------------
# CONFIG
# -------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN or TOKEN.strip() == "":
    raise ValueError("Discord token is missing! Set DISCORD_TOKEN in Railway secrets.")

STAFF_ROLE_ID = 1474517835261804656
DATA_FILE = "data.json"
AUDIT_CHANNEL_ID = 1475295896118755400
GUILD_ID = 123456789012345678  # Replace with your server ID

CARD_TYPES = ["Vanilla", "Sugar", "Sweet", "Sprinkle"]
CARD_COLORS = {
    "Vanilla": ["#F8F0C6", "#FFFDD1", "#FFD3AC", "#FFE5B4"],
    "Sugar": ["#F88379", "#FFB6C1", "#DE5D83", "#FE828C"],
    "Sweet": ["#E6E6FA", "#E6E6FA", "#C8A2C8", "#DC92EF"],
    "Sprinkle": ["#3EB489", "#98FB98", "#E0BBE4", "#FEC8D8"]
}

# -------------------------
# DATA STORAGE
# -------------------------
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
cards = {}

# -------------------------
# BADGES SYSTEM
# -------------------------
def generate_badges():
    badges = {}
    for i in range(1, 501):
        badges[f"open_{i}"] = {"name": f"Opened {i} Cards", "type": "cards_opened", "requirement": i}
    for i in range(1, 301):
        badges[f"give_{i}"] = {"name": f"Gave {i} Cards", "type": "cards_given", "requirement": i}
    for i in range(100, 100001, 500):
        badges[f"sugar_{i}"] = {"name": f"Earned {i} Sugar Bits", "type": "sugar_bits", "requirement": i}
    return badges

BADGES = generate_badges()

# -------------------------
# UTILITIES
# -------------------------
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def get_user(uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {"sugar_bits":0,"bbc":0,"cards_opened":0,"cards_given":0,"badges":[]}
    return data[uid]

async def log_audit(action_type, details):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    message = f"[{ts}] {action_type}: {details}"
    channel = bot.get_channel(AUDIT_CHANNEL_ID)
    if channel:
        try: await channel.send(message)
        except: pass
    with open("audit.log","a") as f: f.write(message + "\n")

async def check_badges(user_id, earned_type=None, earned_amount=0, interaction=None):
    user = get_user(user_id)
    new_badges = []
    for badge_id, badge in BADGES.items():
        if badge_id in user["badges"]: continue
        if earned_type and badge["type"] != earned_type: continue
        prev_amount = user[earned_type]-earned_amount
        if prev_amount < badge["requirement"] <= user[earned_type]:
            user["badges"].append(badge_id)
            new_badges.append(badge["name"])
    if new_badges:
        await log_audit("BADGE_UNLOCKED", f"{user_id} unlocked {', '.join(new_badges)}")
        if interaction:
            try:
                dm = await interaction.user.create_dm()
                await dm.send(f"🎉 You unlocked badge(s): {', '.join(new_badges)}!")
            except: pass
    return new_badges

# -------------------------
# CARD REWARDS
# -------------------------
CARD_PRIZES = {
    "Vanilla": [100,150,200,250,500,1000,5000,10000,20000,50000],
    "Sugar": [300,500,1000,2000,5000,10000],
    "Sweet": [1,2,3,4,5,10,25],
    "Sprinkle": [1,2,3,4,5,10]
}

def generate_rewards(card_type):
    rewards = []
    for i in range(4):
        rewards.append(str(random.choices(CARD_PRIZES[card_type]+["Nothing"], weights=[1]*len(CARD_PRIZES[card_type])+[5], k=1)[0]))
    return rewards

def is_high_value(card_type, value):
    if value=="Nothing": return False
    try: value=int(value)
    except: return False
    if card_type=="Vanilla" and value>=20000: return True
    if card_type=="Sugar" and value>=5000: return True
    return False

# -------------------------
# IMAGE UTILITIES
# -------------------------
def img_to_bytes(img):
    b = io.BytesIO()
    img.save(b, format="PNG")
    b.seek(0)
    return b

def heart_points(x, y, size=30):
    return [
        (x, y + size//4),
        (x + size//2, y - size//4),
        (x + size, y + size//4),
        (x + 3*size//4, y + size),
        (x + size//4, y + size)
    ]

def create_card_image(card_type, scratched, rewards):
    img = Image.new("RGBA",(520,320))
    draw = ImageDraw.Draw(img)
    colors = [hex_to_rgb(c) for c in CARD_COLORS[card_type]]
    for y in range(320):
        pos = y/(319)*(len(colors)-1)
        i = int(pos)
        frac = pos-i
        c = colors[i] if i>=len(colors)-1 else tuple(int(colors[i][j]+(colors[i+1][j]-colors[i][j])*frac) for j in range(3))
        draw.line([(0,y),(520,y)], fill=c)
    font = ImageFont.load_default()
    for i in range(4):
        x = 80 + i*110
        y = 120
        draw.polygon(heart_points(x, y, 60), fill="red")
        if scratched[i]:
            text = "Nothing" if rewards[i]=="Nothing" else str(rewards[i])
            bbox = draw.textbbox((0,0), text, font=font)
            tx = x+30-(bbox[2]/2)
            ty = y+30-(bbox[3]/2)
            if is_high_value(card_type,rewards[i]):
                for offset in range(1,4):
                    draw.text((tx-offset, ty), text, fill="gold", font=font)
                    draw.text((tx+offset, ty), text, fill="gold", font=font)
                    draw.text((tx, ty-offset), text, fill="gold", font=font)
                    draw.text((tx, ty+offset), text, fill="gold", font=font)
            draw.text((tx, ty), text, fill="black", font=font)
    return img

# -------------------------
# CARD VIEW
# -------------------------
class CardDropdown(discord.ui.Select):
    def __init__(self, index, card_type):
        options = [discord.SelectOption(label="Scratch")]
        super().__init__(placeholder="🎀 Scratch Heart", min_values=1, max_values=1, options=options)
        self.index = index
        self.card_type = card_type

    async def callback(self, interaction: discord.Interaction):
        card = cards.get(interaction.message.id)
        if interaction.user != card["user"]:
            return await interaction.response.send_message("Not your card.", ephemeral=True)
        if card["scratched"][self.index]:
            return await interaction.response.send_message("Already scratched.", ephemeral=True)
        card["scratched"][self.index] = True
        img = create_card_image(card["type"], card["scratched"], card["rewards"])
        file = discord.File(img_to_bytes(img),"card.png")
        self.disabled = True
        await interaction.response.edit_message(attachments=[file], view=self.view)
        user_data = get_user(interaction.user.id)
        reward = card["rewards"][self.index]
        if reward != "Nothing":
            if card["type"]=="Vanilla": user_data["sugar_bits"] += int(reward)
            elif card["type"]=="Sugar": user_data["bbc"] += int(reward)
            await check_badges(interaction.user.id, earned_type="sugar_bits" if card["type"]=="Vanilla" else "bbc", earned_amount=int(reward), interaction=interaction)
        user_data["cards_opened"] += 1
        save_data(data)
        await log_audit("CARD_SCRATCHED", f"{interaction.user} scratched {card['type']} card, reward: {reward}")
        if all(card["scratched"]):
            await interaction.followup.send(f"🎉 You completed your {card['type']} card!", ephemeral=True)

class CardView(discord.ui.View):
    def __init__(self, card_type, rewards, user):
        super().__init__(timeout=None)
        self.user = user
        self.card_type = card_type
        self.rewards = rewards
        self.scratched = [False]*4
        for i in range(4):
            self.add_item(CardDropdown(i, card_type))

# -------------------------
# GIVE CARD DROPDROPS
# -------------------------
class RecipientDropdown(discord.ui.Select):
    def __init__(self, staff_user, card_type, guild):
        members = [m for m in guild.members if not m.bot]
        options = [
            discord.SelectOption(label=(m.display_name or m.name)[:100], value=str(m.id))
            for m in members[:25]  # Max 25 options
        ]
        super().__init__(placeholder="🎀 Choose recipient", min_values=1, max_values=1, options=options)
        self.staff_user = staff_user
        self.card_type = card_type

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.staff_user:
            return await interaction.response.send_message("Only the staff who opened this dropdown can select a recipient.", ephemeral=True)
        target_id = int(self.values[0])
        target = interaction.guild.get_member(target_id)
        rewards = generate_rewards(self.card_type)
        view = CardView(self.card_type, rewards, target)
        card_msg = await interaction.channel.send(f"{target.mention}, you received a {self.card_type} card! Scratch the hearts to reveal your rewards.", view=view)
        cards[card_msg.id] = {"user": target, "type": self.card_type, "rewards": rewards, "scratched":[False]*4}
        giver_data = get_user(self.staff_user.id)
        giver_data["cards_given"] += 1
        await check_badges(self.staff_user.id, earned_type="cards_given", earned_amount=1)
        await log_audit("CARD_GIVEN", f"{self.staff_user} gave {self.card_type} card to {target}")
        save_data(data)
        await interaction.response.send_message(f"✅ {self.card_type} card sent to {target.display_name}.", ephemeral=True)

class GiveCardDropdown(discord.ui.Select):
    def __init__(self, staff_user, guild):
        options = [discord.SelectOption(label=ct) for ct in CARD_TYPES]
        super().__init__(placeholder="🎀 Choose a card type...", min_values=1, max_values=1, options=options)
        self.staff_user = staff_user
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.staff_user:
            return await interaction.response.send_message("Only the staff who opened this dropdown can select a card type.", ephemeral=True)
        card_type = self.values[0]
        view = discord.ui.View()
        view.add_item(RecipientDropdown(self.staff_user, card_type, self.guild))
        await interaction.response.edit_message(content=f"Select a recipient for the {card_type} card:", view=view)

class GiveCardView(discord.ui.View):
    def __init__(self, staff_user, guild):
        super().__init__(timeout=None)
        self.add_item(GiveCardDropdown(staff_user, guild))

# -------------------------
# BOT SETUP
# -------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    # Delete old /givecard command
    cmds = await bot.tree.fetch_commands(guild=guild)
    for cmd in cmds:
        if cmd.name == "givecard":
            await bot.tree.delete_command(cmd.id, guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"{bot.user} is online and commands synced!")

@bot.tree.command(name="givecard")
async def givecard_cmd(interaction: discord.Interaction):
    if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message("Only staff can give cards.", ephemeral=True)
    view = GiveCardView(interaction.user, interaction.guild)
    await interaction.response.send_message("Select a card type to give:", view=view, ephemeral=True)

bot.run(TOKEN)