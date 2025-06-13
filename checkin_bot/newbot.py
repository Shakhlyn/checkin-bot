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

check_ins = {}

# # Modal for text input time
# class TimeInputModal(discord.ui.Modal):
#     def __init__(self, status: str):
#         super().__init__(title="Optional Time Input")
#         self.status = status
#
#         self.time_input = discord.ui.InputText(
#             label="Enter time (HH:MM AM/PM or 24h)",
#             placeholder="e.g., 9:45 AM, 14:30, or leave blank",
#             required=False,
#             max_length=8,
#         )
#         self.add_item(self.time_input)
#
#     async def callback(self, interaction: discord.Interaction):
#         user_input = self.time_input.value.strip()
#         await handle_checkin(interaction, self.status, user_input)

# View for dropdown time selection
class TimeSelectView(discord.ui.View):
    def __init__(self, status: str):
        super().__init__(timeout=120)
        self.status = status
        self.hour = None
        self.minute = None
        self.ampm = None

    @discord.ui.select(
        placeholder="Select Hour",
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label=str(h), value=str(h)) for h in range(1, 13)],
        custom_id="select_hour"
    )
    async def select_hour(self, select: discord.ui.Select, interaction: discord.Interaction):
        self.hour = select.values[0]
        await interaction.response.defer()

    @discord.ui.select(
        placeholder="Select Minute",
        min_values=1,
        max_values=1,
        options=[discord.SelectOption(label=f"{m:02}", value=f"{m:02}") for m in range(0, 60, 3)],
        custom_id="select_minute"
    )
    async def select_minute(self, select: discord.ui.Select, interaction: discord.Interaction):
        self.minute = select.values[0]
        await interaction.response.defer()

    @discord.ui.select(
        placeholder="Select AM/PM",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="AM", value="AM"),
            discord.SelectOption(label="PM", value="PM"),
        ],
        custom_id="select_ampm"
    )
    async def select_ampm(self, select: discord.ui.Select, interaction: discord.Interaction):
        self.ampm = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.primary)
    async def submit(self, button: discord.ui.Button, interaction: discord.Interaction):
        if None in (self.hour, self.minute, self.ampm):
            # User did not select full time; fallback to click time
            await handle_checkin(interaction, self.status, None)
        else:
            time_str = f"{self.hour}:{self.minute} {self.ampm}"
            await handle_checkin(interaction, self.status, time_str)

        # Avoid editing ephemeral messages (causes 404)
        if not interaction.message.flags.ephemeral:
            self.disable_all_items()
            await interaction.message.edit(view=self)
        else:
            # Just stop interaction for ephemeral
            self.stop()

# View for selecting input method (TextInput or Dropdown)
class InputMethodView(discord.ui.View):
    def __init__(self, status: str):
        super().__init__(timeout=60)
        self.status = status

    # @discord.ui.button(label="Text Input", style=discord.ButtonStyle.primary)
    # async def text_input_button(self, button: discord.ui.Button, interaction: discord.Interaction):
    #     await interaction.response.send_modal(TimeInputModal(self.status))
    #     self.stop()

    @discord.ui.button(label="Dropdown Select", style=discord.ButtonStyle.secondary)
    async def dropdown_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Select your time:", view=TimeSelectView(self.status), ephemeral=True
        )
        self.stop()

async def handle_checkin(interaction: discord.Interaction, status: str, user_time_str: str | None):
    user = interaction.user
    today = str(date.today())

    if user_time_str:
        # Try parsing user time input with possible formats:
        parsed_time = None
        for fmt in ("%I:%M %p", "%H:%M", "%I:%M%p"):  # 12h with space, 24h, 12h no space
            try:
                parsed_time = datetime.strptime(user_time_str, fmt)
                break
            except Exception:
                continue
        if parsed_time is None:
            # Failed to parse, inform user and abort
            await interaction.response.send_message(
                "❌ Invalid time format. Please use formats like `9:45 AM`, `09:45 PM`, or `14:30`.",
                ephemeral=True
            )
            return

        # Format time string consistently in 24h format HH:mm
        time_str = parsed_time.strftime("%H:%M")
    else:
        # No user time given, use current time
        now = datetime.now()
        time_str = now.strftime("%H:%M")

    # Store check-in
    check_ins.setdefault(today, {})[user.id] = {
        "status": status,
        "time": time_str,
        "name": user.name,
    }

    await interaction.response.send_message(
        f"{user.mention} checked `{status}` at `{time_str}`", ephemeral=True
    )
    print(f"[{today}] {user.name} marked {status} at {time_str}")

class CheckInButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🟢 In", style=discord.ButtonStyle.success, custom_id="btn_in")
    async def in_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Choose how you'd like to provide your check-in time:",
            view=TimeSelectView("in"),
            ephemeral=True,
        )

    @discord.ui.button(label="🔴 Out", style=discord.ButtonStyle.danger, custom_id="btn_out")
    async def out_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Choose how you'd like to provide your check-out time:",
            view=TimeSelectView("out"),
            ephemeral=True,
        )

async def send_daily_checkin():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("📋 **Daily Check-In** — click below:", view=CheckInButtons())
    else:
        print("❌ Could not find channel to send check-in message.")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await send_daily_checkin()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_checkin, "cron", hour=9, minute=0, day_of_week="mon-fri")
    scheduler.start()

bot.run(TOKEN)
