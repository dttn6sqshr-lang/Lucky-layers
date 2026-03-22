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
async def log_action(message: str):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(message)

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
        choices = [p[0] for p in pool]
        weights = [p[1] for p in pool]
        rewards.append(random.choices(choices, weights=weights)[0])
    return rewards

def is_rare(value):
    return value not in ["Nothing", "100"]

# -------------------------
# HEART DRAWING
# -------------------------
def draw_heart(draw, x, y, size, color):
    draw.ellipse((x, y, x+size//2, y+size//2), fill=color)
    draw.ellipse((x+size//2, y, x+size, y+size//2), fill=color)
    draw.polygon([(x, y+size//3),(x+size, y+size//3),(x+size//2, y+size)], fill=color)

# -------------------------
# CREATE CARD IMAGE (Option C)
# -------------------------
def create_card(card_type, scratched, rewards):
    img = Image.new("RGBA", (520, 320))
    draw = ImageDraw.Draw(img)

    base_colors = {
        "Vanilla": (255,240,200),
        "Sugar": (255,182,193),
        "Sweet": (220,200,255),
        "Sprinkle": (200,255,230)
    }
    base = base_colors.get(card_type, (255,200,200))
    for y in range(320):
        shade = tuple(min(255,c+int(y*0.1)) for c in base)
        draw.line([(0,y),(520,y)], fill=shade)

    font = ImageFont.load_default()
    heart_size = 50
    padding_x = 30
    padding_y = 100
    gap = 60

    for i in range(8):
        row = i // 4
        col = i % 4
        x = padding_x + col * gap
        y = padding_y + row * (heart_size + 20)

        # Heart
        draw_heart(draw, x, y, heart_size, (255,60,100))

        # Reward if scratched
        if scratched[i]:
            text = rewards[i]
            if is_rare(text):
                for glow in range(3):
                    draw.text((x+10-glow, y+15), text, fill="gold", font=font)
            draw.text((x+10, y+15), text, fill="black", font=font)

    return img

def img_bytes(img):
    b = io.BytesIO()
    img.save(b,"PNG")
    b.seek(0)
    return b

# -------------------------
# SCRATCH BUTTON
# -------------------------
class ScratchButton(discord.ui.Button):
    def __init__(self,index):
        super().__init__(label="💖", style=discord.ButtonStyle.secondary)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        card = cards.get(interaction.message.id)
        if interaction.user != card["user"]:
            await interaction.response.send_message("⚠️ Not your card!", ephemeral=True)
            await log_action(f"⚠️ {interaction.user} tried to scratch someone else's card")
            return

        if card["scratched"][self.index]:
            return await interaction.response.send_message("Already scratched.", ephemeral=True)

        card["scratched"][self.index] = True

        # Animate reveal (fade-style)
        for _ in range(3):
            img = create_card(card["type"], card["scratched"], card["rewards"])
            file = discord.File(img_bytes(img),"card.png")
            await interaction.message.edit(attachments=[file], view=self.view)
            await asyncio.sleep(0.2)

        self.disabled = True

        reward = card["rewards"][self.index]
        user = get_user(interaction.user.id)
        if reward != "Nothing":
            user["sugar"] += int(reward)
            await log_action(f"✨ {interaction.user} scratched heart {self.index+1} and got {reward} sugar")
        else:
            await log_action(f"✂️ {interaction.user} scratched heart {self.index+1} and got Nothing")

        user["opened"] += 1

        # Badge unlock
        if user["sugar"] >= 1000 and "1000_sugar" not in user["badges"]:
            user["badges"].append("1000_sugar")
            await interaction.user.send_message(f"🏅 Congratulations! You unlocked the **1000 sugar** badge!")
            await log_action(f"🏅 {interaction.user} unlocked 1000 sugar badge")

        if all(card["scratched"]):
            for child in self.view.children:
                child.disabled = True
            await interaction.followup.send("🎉 Card complete!", ephemeral=True)

# -------------------------
# CARD VIEW
# -------------------------
class CardView(discord.ui.View):
    def __init__(self,user,rewards,card_type):
        super().__init__(timeout=None)
        self.user = user
        for i in range(8):
            self.add_item(ScratchButton(i))

# -------------------------
# USER PICKER
# -------------------------
class UserPicker(discord.ui.UserSelect):
    def __init__(self,staff_user,card_type):
        super().__init__(placeholder="🎀 Select recipient", min_values=1, max_values=1)
        self.staff_user = staff_user
        self.card_type = card_type

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.staff_user:
            return await interaction.response.send_message("⚠️ Not your menu.", ephemeral=True)

        target = self.values[0]
        rewards = generate_rewards()
        view = CardView(target,rewards,self.card_type)
        img = create_card(self.card_type,[False]*8,rewards)
        file = discord.File(img_bytes(img),"card.png")
        msg = await interaction.channel.send(
            f"✦🌸✧  **A sweet surprise appears!**\n💌 {target.mention} received a **{self.card_type}** card 💖!",
            file=file,
            view=view
        )
        cards[msg.id] = {"user":target,"type":self.card_type,"rewards":rewards,"scratched":[False]*8}
        giver = get_user(interaction.user.id)
        giver["given"] += 1
        await interaction.response.send_message("✅ Sent!", ephemeral=True)
        await log_action(f"💌 {interaction.user} gave a {self.card_type} card to {target}")

# -------------------------
# CARD TYPE DROPDOWN
# -------------------------
class CardTypeDropdown(discord.ui.Select):
    def __init__(self,staff_user):
        options = [discord.SelectOption(label=t) for t in ["Vanilla","Sugar","Sweet","Sprinkle"]]
        super().__init__(placeholder="🎀 Choose card type", options=options)
        self.staff_user = staff_user

    async def callback(self, interaction: discord.Interaction):
        card_type = self.values[0]
        view = discord.ui.View()
        view.add_item(UserPicker(self.staff_user,card_type))
        await interaction.response.edit_message(content=f"🎀 Choose recipient for {card_type} card:", view=view)

class GiveCardView(discord.ui.View):
    def __init__(self,staff_user):
        super().__init__(timeout=None)
        self.add_item(CardTypeDropdown(staff_user))

# -------------------------
# COMMANDS
# -------------------------
@bot.tree.command(name="givecard", guild=discord.Object(id=GUILD_ID))
async def givecard(interaction: discord.Interaction):
    if not any(role.id==STAFF_ROLE_ID for role in interaction.user.roles):
        return await interaction.response.send_message("⚠️ Staff only.", ephemeral=True)
    await interaction.response.send_message("🎀 Choose a card type:", view=GiveCardView(interaction.user), ephemeral=True)

@bot.tree.command(name="profile", guild=discord.Object(id=GUILD_ID))
async def profile(interaction: discord.Interaction):
    user = get_user(interaction.user.id)
    badges = ", ".join(user["badges"]) if user["badges"] else "None"
    await interaction.response.send_message(
        f"♱  ̥  **{interaction.user}’s sweet stats:**\n💖 Sugar: **{user['sugar']}**\n🎴 Cards opened: **{user['opened']}**\n🎁 Cards given: **{user['given']}**\n🏅 Badges: {badges}"
    )
    await log_action(f"📜 {interaction.user} viewed their profile")

@bot.tree.command(name="leaderboard", guild=discord.Object(id=GUILD_ID))
async def leaderboard(interaction: discord.Interaction):
    sorted_users = sorted(data.items(), key=lambda x:x[1]["sugar"], reverse=True)[:10]
    text = "𐔌 🎀  **Top Sugar Collectors**\n"
    for i,(uid,stats) in enumerate(sorted_users,1):
        text += f"{i}️⃣ <@{uid}> — **{stats['sugar']} 💖**\n"
    await interaction.response.send_message(text or "No data yet!")
    await log_action(f"📊 {interaction.user} viewed the leaderboard")

# -------------------------
# READY
# -------------------------
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    print("✅ Commands synced")
    print(f"🚀 Logged in as {bot.user}")

bot.run(TOKEN)