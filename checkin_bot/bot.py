import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Store status as {date: {user_id: {'status': 'in'/'out', 'time': str}}}
check_ins = {}

class CheckInButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🟢 In", style=discord.ButtonStyle.success, custom_id="btn_in")
    async def in_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.set_status(interaction, "in")

    @discord.ui.button(label="🔴 Out", style=discord.ButtonStyle.danger, custom_id="btn_out")
    async def out_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.set_status(interaction, "out")

    async def set_status(self, interaction: discord.Interaction, status: str):
        user = interaction.user
        now = datetime.now()
        today = str(date.today())
        check_ins.setdefault(today, {})[user.id] = {
            "status": status,
            "time": now.strftime("%H:%M:%S"),
            "name": user.name
        }

        await interaction.response.send_message(
            f"{user.mention} checked `{status}` at `{now.strftime('%H:%M:%S')}`", ephemeral=True
        )

        print(f"[{today}] {user.name} marked {status} at {now.strftime('%H:%M:%S')}")

async def send_daily_checkin():
    """Sends a fresh check-in message each day."""
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("📋 **Daily Check-In** — click below:", view=CheckInButtons())
    else:
        print("❌ Could not find channel to send check-in message.")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    # Send today's check-in if not already done
    await send_daily_checkin()

    # Schedule new message every weekday at 9:00 AM
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_checkin, "cron", hour=9, minute=0, day_of_week='mon-fri')
    scheduler.start()

bot.run(TOKEN)
