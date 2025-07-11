import discord
from discord.ext import commands, tasks
from discord import ui, ButtonStyle, Interaction, Embed
import json
from datetime import datetime, timedelta
import requests
import yfinance as yf
import time
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

DATA_FILE = 'schedule.json'
STOCKS_FILE = 'stocks.json'
REMINDERS_FILE = 'reminders.json'
CHANNEL_ID = 1392921483524833324  # Your server channel id for updates

# APIs
OPENWEATHER_API_KEY = '310a9cfcca089689ccbc59cc6ce3139a'  # Replace with your key
WEATHER_USAGE_FILE = 'weather_usage.json'
MAX_CALLS_PER_MINUTE = 10
WARN_THRESHOLD = 700_000
HARD_LIMIT = 900_000

# Load schedule data
try:
    with open(DATA_FILE, 'r') as f:
        schedule = json.load(f)
except FileNotFoundError:
    schedule = {}

# Load stocks watchlist
try:
    with open(STOCKS_FILE, 'r') as f:
        stocks = json.load(f)
except FileNotFoundError:
    stocks = {}

# Load reminders
try:
    with open(REMINDERS_FILE, 'r') as f:
        reminders = json.load(f)
except FileNotFoundError:
    reminders = []

def save_schedule():
    with open(DATA_FILE, 'w') as f:
        json.dump(schedule, f, indent=4)

def save_stocks():
    with open(STOCKS_FILE, 'w') as f:
        json.dump(stocks, f, indent=4)

def save_reminders():
    with open(REMINDERS_FILE, 'w') as f:
        json.dump(reminders, f, indent=4)

def validate_date(date_str):
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_datetime(datetime_str):
    try:
        datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        return True
    except ValueError:
        return False

# Load weather call tracking
try:
    with open(WEATHER_USAGE_FILE, 'r') as f:
        weather_call_log = json.load(f)
except FileNotFoundError:
    weather_call_log = {
        "minute_window": [],
        "monthly_count": 0,
        "last_reset": ""
    }

def save_weather_usage():
    with open(WEATHER_USAGE_FILE, 'w') as f:
        json.dump(weather_call_log, f)

def can_make_weather_call():
    now = time.time()
    current_month = datetime.now().strftime('%Y-%m')
    if weather_call_log.get("last_reset") != current_month:
        weather_call_log["monthly_count"] = 0
        weather_call_log["last_reset"] = current_month

    if weather_call_log["monthly_count"] >= HARD_LIMIT:
        return False, "⛔ Weather API limit reached (900,000/month)."

    weather_call_log["minute_window"] = [
        t for t in weather_call_log["minute_window"] if now - t < 60
    ]

    if len(weather_call_log["minute_window"]) >= MAX_CALLS_PER_MINUTE:
        return False, "⚠️ Too many weather calls this minute. Try again soon."

    weather_call_log["minute_window"].append(now)
    weather_call_log["monthly_count"] += 1
    save_weather_usage()

    if weather_call_log["monthly_count"] >= WARN_THRESHOLD:
        return True, f"⚠️ Approaching monthly weather API limit: {weather_call_log['monthly_count']} calls."

    return True, None

### --- ENHANCED UI VIEWS --- ###

class MainControlPanel(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📋 Tasks", style=ButtonStyle.primary, custom_id="main_tasks")
    async def tasks_button(self, interaction: Interaction, button: ui.Button):
        view = TasksView()
        embed = Embed(title="📋 Task Management", description="Choose an action:", color=0x3498db)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="📅 Schedule", style=ButtonStyle.secondary, custom_id="main_schedule")
    async def schedule_button(self, interaction: Interaction, button: ui.Button):
        # Get today, tomorrow, and the day after
        days = [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(3)]
        day_labels = ["Today", "Tomorrow", "Day After"]

        embed = Embed(title="📅 Your 3-Day Schedule", color=0x2ecc71)

        for day, label in zip(days, day_labels):
            day_tasks = []
            for cat in schedule:
                if day in schedule[cat]:
                    for task in schedule[cat][day]:
                        day_tasks.append(f"**{cat.title()}** - {task['task']}")
            if day_tasks:
                embed.add_field(name=f"{label} ({day})", value="\n".join(day_tasks[:5]), inline=True)
            else:
                embed.add_field(name=f"{label} ({day})", value="No tasks scheduled", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


    @ui.button(label="🌤️ Weather", style=ButtonStyle.success, custom_id="main_weather")
    async def weather_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(WeatherModal())

    @ui.button(label="📈 Stocks", style=ButtonStyle.danger, custom_id="main_stocks")
    async def stocks_button(self, interaction: Interaction, button: ui.Button):
        if not stocks:
            await interaction.response.send_message(
                "📉 Your stock watchlist is empty. Use `!addstock SYMBOL` to add stocks.", ephemeral=True)
            return

        embed = Embed(title="📈 Stock Prices", color=0xe74c3c)
        stock_info = []

        for symbol in list(stocks.keys())[:10]:  # Limit to avoid hitting API too hard
            try:
                stock = yf.Ticker(symbol)
                price = stock.fast_info.get('lastPrice') or stock.info.get('regularMarketPrice')
                if price is None:
                    price = "N/A"
                stock_info.append(f"**{symbol}**: ${price}")
            except Exception as e:
                stock_info.append(f"❌ **{symbol}**: Error fetching ({type(e).__name__})")

        embed.description = "\n".join(stock_info)
        await interaction.response.send_message(embed=embed, ephemeral=True)



    @ui.button(label="⏰ Reminders", style=ButtonStyle.secondary, custom_id="main_reminders")
    async def reminders_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(ReminderModal())

    @ui.button(label="❓ Help", style=ButtonStyle.secondary, custom_id="main_help")
    async def help_button(self, interaction: Interaction, button: ui.Button):
        embed = Embed(title="🤖 Bot Commands & Help", color=0x9b59b6)
        
        embed.add_field(
            name="📋 Task Commands",
            value="`!addtask <category> <date> <task>` - Add a task\n"
                  "`!addsubtask <category> <date> <task#> <subtask>` - Add subtask\n"
                  "`!schedule [category] [date]` - View schedule\n"
                  "`!removetask <category> <date> <task#>` - Remove task\n"
                  "`!edittask <category> <date> <task#> <new_task>` - Edit task",
            inline=False
        )
        
        embed.add_field(
            name="📈 Stock Commands",
            value="`!addstock <SYMBOL> [buy_below] [sell_above]` - Add stock to watchlist\n"
                  "`!removestock <SYMBOL>` - Remove stock from watchlist\n"
                  "`!stocks` - View all stocks in watchlist",
            inline=False
        )
        
        embed.add_field(
            name="🌤️ Weather Commands",
            value="`!weather [city]` - Get weather (defaults to Windsor, ON)\n"
                  "Use the Weather button for quick access!",
            inline=False
        )
        
        embed.add_field(
            name="⏰ Reminder Commands",
            value="`!remind <YYYY-MM-DD HH:MM> <message>` - Set a reminder\n"
                  "`!reminders` - View active reminders\n"
                  "`!cancelreminder <number>` - Cancel a reminder",
            inline=False
        )
        
        embed.add_field(
            name="📊 Other Commands",
            value="`!daily` - Get daily summary\n"
                  "`!status` - Show this control panel\n"
                  "`!stats` - Show bot usage statistics",
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="• Use buttons for quick actions\n"
                  "• Date format: YYYY-MM-DD (e.g., 2025-07-10)\n"
                  "• Stock symbols should be uppercase (e.g., AAPL)\n"
                  "• The bot checks stocks every 15 minutes\n"
                  "• Weather API has monthly limits - use wisely!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class TasksView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="➕ Add Task", style=ButtonStyle.primary)
    async def add_task_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(TaskModal())

    @ui.button(label="📋 View Tasks", style=ButtonStyle.secondary)
    async def view_tasks_button(self, interaction: Interaction, button: ui.Button):
        if not schedule:
            await interaction.response.send_message("📅 Your schedule is empty.", ephemeral=True)
            return

        # Flatten and sort all tasks by date ascending
        all_tasks = []
        for cat, dates in schedule.items():
            for date_str, tasks_list in dates.items():
                for idx, task in enumerate(tasks_list):
                    all_tasks.append({
                        "category": cat.title(),
                        "date": date_str,
                        "task": task['task'],
                        "index": idx
                    })
        all_tasks.sort(key=lambda x: x['date'])  # Soonest first

        # Embed for header
        embed = Embed(title="📋 All Tasks", color=0x3498db)
        embed.description = "Click any button below to edit that task."

        # Create a view with buttons for each task
        view = ui.View(timeout=180)
        colors = [ButtonStyle.primary, ButtonStyle.success, ButtonStyle.danger, ButtonStyle.secondary]
        for i, t in enumerate(all_tasks):
            button = ui.Button(
                label=f"{t['date']} - {t['task'][:20]}...",
                style=colors[i % len(colors)],
                custom_id=f"edit_{t['category']}_{t['date']}_{t['index']}"
            )
            async def button_callback(inter, task=t):
                await inter.response.send_modal(EditTaskModal(task))
            button.callback = button_callback
            view.add_item(button)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

### --- ENHANCED MODALS --- ###
class EditTaskView(ui.View):
    def __init__(self, tasks):
        super().__init__(timeout=120)
        colors = [ButtonStyle.primary, ButtonStyle.success, ButtonStyle.danger, ButtonStyle.secondary]
        for idx, t in enumerate(tasks[:20]):  # Limit to 20 buttons
            self.add_item(ui.Button(
                label=f"{t['category']} ({t['date']})",
                style=colors[idx % len(colors)],
                custom_id=f"edit_{idx}"
            ))

    @ui.button(label="🔄 Refresh", style=ButtonStyle.primary)
    async def refresh_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        view = TasksView()
        await view.view_tasks_button.callback(interaction, button)
    
    async def interaction_check(self, interaction: Interaction):
        if interaction.data['custom_id'].startswith('edit_'):
            index = int(interaction.data['custom_id'].split('_')[1])
            modal = EditTaskModal(self.children[index], index)
            await interaction.response.send_modal(modal)
            return False  # Stop further processing
        return True

class EditTaskModal(ui.Modal, title="Edit Task"):
    new_task = ui.TextInput(label="New Task Description", style=discord.TextStyle.long, required=True)

    def __init__(self, task):
        super().__init__()
        self.task = task

    async def on_submit(self, interaction: Interaction):
        category = self.task['category'].lower()
        date = self.task['date']
        index = self.task['index']
        old_task = schedule[category][date][index]['task']
        schedule[category][date][index]['task'] = self.new_task.value
        save_schedule()
        await interaction.response.send_message(
            f"✅ Updated task:\n**Old:** {old_task}\n**New:** {self.new_task.value}", ephemeral=True
        )

class TaskModal(ui.Modal, title="Add New Task"):
    category = ui.TextInput(label="Category", placeholder="e.g. work, personal, study", required=True)
    date = ui.TextInput(label="Date (YYYY-MM-DD)", placeholder="2025-07-10", required=True)
    task_description = ui.TextInput(label="Task Description", style=discord.TextStyle.long, required=True)

    async def on_submit(self, interaction: Interaction):
        cat = self.category.value.lower()
        date = self.date.value
        task = self.task_description.value
        
        if not validate_date(date):
            await interaction.response.send_message("❌ Invalid date format! Use YYYY-MM-DD.", ephemeral=True)
            return

        if cat not in schedule:
            schedule[cat] = {}
        schedule[cat].setdefault(date, []).append({"task": task, "subtasks": []})
        save_schedule()
        await interaction.response.send_message(f"✅ Added task to **{cat}** on **{date}**: {task}", ephemeral=True)

class WeatherModal(ui.Modal, title="Get Weather"):
    city = ui.TextInput(label="City", placeholder="Leave empty for Windsor, ON", required=False)

    async def on_submit(self, interaction: Interaction):
        city = self.city.value or "Windsor, Ontario"
        
        allowed, message = can_make_weather_call()
        if not allowed:
            await interaction.response.send_message(message, ephemeral=True)
            return
        
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        response = requests.get(url).json()
        
        if response.get("cod") != 200:
            await interaction.response.send_message("❌ Could not get weather for that location.", ephemeral=True)
            return
        
        weather_desc = response['weather'][0]['description'].capitalize()
        temp = response['main']['temp']
        feels_like = response['main']['feels_like']
        humidity = response['main']['humidity']
        wind = response['wind']['speed']
        
        embed = Embed(title=f"🌤️ Weather in {city.title()}", color=0x3498db)
        embed.add_field(name="Condition", value=weather_desc, inline=True)
        embed.add_field(name="Temperature", value=f"{temp}°C", inline=True)
        embed.add_field(name="Feels Like", value=f"{feels_like}°C", inline=True)
        embed.add_field(name="Humidity", value=f"{humidity}%", inline=True)
        embed.add_field(name="Wind Speed", value=f"{wind} m/s", inline=True)
        
        if message:  # Warning message
            embed.set_footer(text=message)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ReminderModal(ui.Modal, title="Set Reminder"):
    datetime_input = ui.TextInput(label="Date & Time (YYYY-MM-DD HH:MM)", placeholder="2025-07-10 14:30", required=True)
    message_input = ui.TextInput(label="Reminder Message", style=discord.TextStyle.long, required=True)

    async def on_submit(self, interaction: Interaction):
        datetime_str = self.datetime_input.value
        message = self.message_input.value
        
        if not validate_datetime(datetime_str):
            await interaction.response.send_message("❌ Invalid datetime format! Use YYYY-MM-DD HH:MM.", ephemeral=True)
            return
        
        reminder_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        if reminder_time <= datetime.now():
            await interaction.response.send_message("❌ Reminder time must be in the future!", ephemeral=True)
            return
        
        reminder = {
            "id": len(reminders) + 1,
            "datetime": datetime_str,
            "message": message,
            "created": datetime.now().isoformat()
        }
        
        reminders.append(reminder)
        save_reminders()
        
        await interaction.response.send_message(f"⏰ Reminder set for **{datetime_str}**: {message}", ephemeral=True)

### --- EXISTING COMMANDS (keeping all your original functionality) --- ###

@bot.command(name='addtask')
async def add_task(ctx, category: str, date: str, *, task: str):
    """Add a task under a category with date (YYYY-MM-DD). Usage: !addtask work 2025-07-10 Finish report"""
    category = category.lower()
    if not validate_date(date):
        await ctx.send("❌ Invalid date format! Please use YYYY-MM-DD.")
        return
    if category not in schedule:
        schedule[category] = {}
    schedule[category].setdefault(date, []).append({"task": task, "subtasks": []})
    save_schedule()
    await ctx.send(f"✅ Added task to **{category}** on **{date}**: {task}")

@bot.command(name='addsubtask')
async def add_subtask(ctx, category: str, date: str, task_number: int, *, subtask: str):
    """Add a subtask to a task. Usage: !addsubtask work 2025-07-10 1 Write introduction"""
    category = category.lower()
    if category not in schedule or date not in schedule[category]:
        await ctx.send("❌ Task or category not found.")
        return
    tasks = schedule[category][date]
    if task_number < 1 or task_number > len(tasks):
        await ctx.send("❌ Invalid task number.")
        return
    tasks[task_number - 1]['subtasks'].append(subtask)
    save_schedule()
    await ctx.send(f"✅ Added subtask to task #{task_number} in **{category}** on **{date}**: {subtask}")

@bot.command(name='schedule')
async def view_schedule(ctx, category: str = None, date: str = None):
    """View tasks by category and/or date. Usage: !schedule [category] [date]"""
    if category:
        category = category.lower()
        if category not in schedule:
            await ctx.send(f"❌ No tasks found under category **{category}**.")
            return
        cat_tasks = schedule[category]
        if date:
            if not validate_date(date):
                await ctx.send("❌ Invalid date format! Use YYYY-MM-DD.")
                return
            tasks = cat_tasks.get(date)
            if not tasks:
                await ctx.send(f"📅 No tasks for **{category}** on **{date}**.")
                return
            msg = f"**{category.title()} tasks on {date}:**\n"
            for i, t in enumerate(tasks, 1):
                msg += f"{i}. {t['task']}\n"
                for si, st in enumerate(t['subtasks'], 1):
                    msg += f"    - {si}. {st}\n"
            await ctx.send(msg)
        else:
            msg = f"**All tasks in category {category}:**\n"
            for d in sorted(cat_tasks):
                msg += f"__{d}__\n"
                for i, t in enumerate(cat_tasks[d], 1):
                    msg += f"{i}. {t['task']}\n"
                    for si, st in enumerate(t['subtasks'], 1):
                        msg += f"    - {si}. {st}\n"
            await ctx.send(msg)
    else:
        if not schedule:
            await ctx.send("📅 Your schedule is empty.")
            return
        msg = "**Full Schedule:**\n"
        for cat in schedule:
            msg += f"__Category: {cat.title()}__\n"
            for d in sorted(schedule[cat]):
                msg += f"  __{d}__\n"
                for i, t in enumerate(schedule[cat][d], 1):
                    msg += f"  {i}. {t['task']}\n"
                    for si, st in enumerate(t['subtasks'], 1):
                        msg += f"      - {si}. {st}\n"
        await ctx.send(msg)

@bot.command(name='removetask')
async def remove_task(ctx, category: str, date: str, task_number: int):
    """Remove a task by number in category/date. Usage: !removetask work 2025-07-10 1"""
    category = category.lower()
    if category not in schedule or date not in schedule[category]:
        await ctx.send("❌ Task or category not found.")
        return
    tasks = schedule[category][date]
    if task_number < 1 or task_number > len(tasks):
        await ctx.send("❌ Invalid task number.")
        return
    removed = tasks.pop(task_number - 1)
    if not tasks:
        del schedule[category][date]
    if not schedule[category]:
        del schedule[category]
    save_schedule()
    await ctx.send(f"🗑️ Removed task #{task_number} from **{category}** on **{date}**: {removed['task']}")

@bot.command(name='edittask')
async def edit_task(ctx, category: str, date: str, task_number: int, *, new_task: str):
    """Edit a task. Usage: !edittask work 2025-07-10 1 New task description"""
    category = category.lower()
    if category not in schedule or date not in schedule[category]:
        await ctx.send("❌ Task or category not found.")
        return
    tasks = schedule[category][date]
    if task_number < 1 or task_number > len(tasks):
        await ctx.send("❌ Invalid task number.")
        return
    old_task = tasks[task_number - 1]['task']
    tasks[task_number - 1]['task'] = new_task
    save_schedule()
    await ctx.send(f"✅ Updated task #{task_number} on **{category}**/**{date}**:\n- Old: {old_task}\n- New: {new_task}")

@bot.command(name='weather')
async def get_weather(ctx, *, city: str = None):
    """Get current weather for a city or default to Windsor, Ontario if none provided."""
    if not city:
        city = "Windsor, Ontario"
    allowed, message = can_make_weather_call()
    if not allowed:
        await ctx.send(message)
        return
    elif message:
        await ctx.send(message)

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    response = requests.get(url).json()
    if response.get("cod") != 200:
        await ctx.send("❌ Could not get weather for that location.")
        return
    weather_desc = response['weather'][0]['description'].capitalize()
    temp = response['main']['temp']
    humidity = response['main']['humidity']
    wind = response['wind']['speed']
    await ctx.send(f"🌤 Weather in **{city.title()}**:\nCondition: {weather_desc}\nTemperature: {temp}°C\nHumidity: {humidity}%\nWind speed: {wind} m/s")

@bot.command(name='addstock')
async def add_stock(ctx, symbol: str, buy_below: float = None, sell_above: float = None):
    """Add a stock to watchlist with optional buy/sell thresholds. Usage: !addstock AAPL 150 170"""
    symbol = symbol.upper()
    stocks[symbol] = {"buy_below": buy_below, "sell_above": sell_above}
    save_stocks()
    await ctx.send(f"📈 Added stock **{symbol}** to watchlist. Buy below: {buy_below}, Sell above: {sell_above}")

@bot.command(name='removestock')
async def remove_stock(ctx, symbol: str):
    """Remove stock from watchlist. Usage: !removestock AAPL"""
    symbol = symbol.upper()
    if symbol in stocks:
        del stocks[symbol]
        save_stocks()
        await ctx.send(f"🗑️ Removed **{symbol}** from watchlist.")
    else:
        await ctx.send("❌ Stock not found in watchlist.")

@bot.command(name='stocks')
async def list_stocks(ctx):
    """List all stocks in watchlist."""
    if not stocks:
        await ctx.send("📉 Your stock watchlist is empty.")
        return
    msg = "**Stock Watchlist:**\n"
    for s, v in stocks.items():
        msg += f"{s} — Buy below: {v['buy_below']}, Sell above: {v['sell_above']}\n"
    await ctx.send(msg)

### --- NEW REMINDER COMMANDS --- ###

@bot.command(name='remind')
async def set_reminder(ctx, datetime_str: str, time_str: str, *, message: str):
    """Set a reminder. Usage: !remind 2025-07-10 14:30 Important meeting"""
    full_datetime = f"{datetime_str} {time_str}"
    if not validate_datetime(full_datetime):
        await ctx.send("❌ Invalid datetime format! Use YYYY-MM-DD HH:MM.")
        return
    
    reminder_time = datetime.strptime(full_datetime, '%Y-%m-%d %H:%M')
    if reminder_time <= datetime.now():
        await ctx.send("❌ Reminder time must be in the future!")
        return
    
    reminder = {
        "id": len(reminders) + 1,
        "datetime": full_datetime,
        "message": message,
        "created": datetime.now().isoformat()
    }
    
    reminders.append(reminder)
    save_reminders()
    await ctx.send(f"⏰ Reminder set for **{full_datetime}**: {message}")

@bot.command(name='reminders')
async def list_reminders(ctx):
    """List all active reminders."""
    if not reminders:
        await ctx.send("⏰ No active reminders.")
        return
    
    msg = "**Active Reminders:**\n"
    for r in reminders:
        msg += f"{r['id']}. **{r['datetime']}** - {r['message']}\n"
    await ctx.send(msg)

@bot.command(name='cancelreminder')
async def cancel_reminder(ctx, reminder_id: int):
    """Cancel a reminder by ID. Usage: !cancelreminder 1"""
    global reminders
    reminders = [r for r in reminders if r['id'] != reminder_id]
    save_reminders()
    await ctx.send(f"❌ Cancelled reminder #{reminder_id}")

### --- NEW UTILITY COMMANDS --- ###

@bot.command(name='status')
async def show_status(ctx):
    """Show the main control panel."""
    embed = Embed(title="🤖 Personal Assistant Control Panel", 
                  description="Use the buttons below to quickly access different features!", 
                  color=0x3498db)
    view = MainControlPanel()
    await ctx.send(embed=embed, view=view)

@bot.command(name='stats')
async def show_stats(ctx):
    """Show bot usage statistics."""
    total_tasks = sum(len(tasks) for cat in schedule.values() for tasks in cat.values())
    total_stocks = len(stocks)
    total_reminders = len(reminders)
    weather_calls = weather_call_log.get("monthly_count", 0)
    
    embed = Embed(title="📊 Bot Statistics", color=0x9b59b6)
    embed.add_field(name="📋 Total Tasks", value=str(total_tasks), inline=True)
    embed.add_field(name="📈 Stocks Tracked", value=str(total_stocks), inline=True)
    embed.add_field(name="⏰ Active Reminders", value=str(total_reminders), inline=True)
    embed.add_field(name="🌤️ Weather Calls This Month", value=str(weather_calls), inline=True)
    
    await ctx.send(embed=embed)

### --- BACKGROUND TASKS --- ###

@tasks.loop(minutes=15)
async def stock_price_check():
    """Background task to check stock prices and alert if thresholds hit."""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    alerts = []
    for symbol, limits in stocks.items():
        try:
            stock = yf.Ticker(symbol)
            price = stock.info.get('regularMarketPrice')
            if price is None:
                continue
            buy = limits.get('buy_below')
            sell = limits.get('sell_above')

            if buy is not None and price < buy:
                alerts.append(f"📉 **{symbol}** price is **${price:.2f}**, below buy threshold ${buy}!")
            if sell is not None and price > sell:
                alerts.append(f"📈 **{symbol}** price is **${price:.2f}**, above sell threshold ${sell}!")
        except Exception as e:
            print(f"Error fetching stock {symbol}: {e}")

    if alerts:
        await channel.send("\n".join(alerts))

@tasks.loop(minutes=1)
async def check_reminders():
    """Check for due reminders every minute."""
    global reminders
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
    
    now = datetime.now()
    due_reminders = []
    
    for reminder in reminders[:]:  # Copy to avoid modification during iteration
        reminder_time = datetime.strptime(reminder['datetime'], '%Y-%m-%d %H:%M')
        if reminder_time <= now:
            due_reminders.append(reminder)
            reminders.remove(reminder)
    
    if due_reminders:
        save_reminders()
        for reminder in due_reminders:
            embed = Embed(title="⏰ Reminder!", description=reminder['message'], color=0xf39c12)
            await channel.send(f"<@{bot.user.id}>", embed=embed)

@bot.command(name='daily')
async def daily_summary(ctx):
    """Get a daily summary of weather, stocks, and tasks."""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        await ctx.send("❌ Channel not found.")
        return

    city = "Windsor, Ontario"
    allowed, message = can_make_weather_call()
    if not allowed:
        weather_msg = message
    else:
        if message:
            await ctx.send(message)
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        w = requests.get(weather_url).json()
        if w.get("cod") == 200:
            weather_desc = w['weather'][0]['description'].capitalize()
            temp = w['main']['temp']
            weather_msg = f"🌤 Weather in **{city}**: {weather_desc}, {temp}°C"
        else:
            weather_msg = "Could not get weather info."

    # Stock summary
    stock_msg = ""
    for symbol in stocks:
        try:
            price = yf.Ticker(symbol).info.get('regularMarketPrice')
            if price:
                stock_msg += f"{symbol}: ${price:.2f}\n"
        except:
            stock_msg += f"{symbol}: Error fetching price\n"
    if not stock_msg:
        stock_msg = "No stocks in watchlist."

    # Tasks summary: show tasks for today
    today = datetime.now().strftime('%Y-%m-%d')
    task_msg = ""
    for cat in schedule:
        if today in schedule[cat]:
            task_msg += f"__{cat.title()}__\n"
            for i, t in enumerate(schedule[cat][today], 1):
                task_msg += f"{i}. {t['task']}\n"
                for si, st in enumerate(t['subtasks'], 1):
                    task_msg += f"    - {si}. {st}\n"
    if not task_msg:
        task_msg = "No tasks for today."

    # Reminder summary
    reminder_msg = ""
    today_reminders = [r for r in reminders if r['datetime'].startswith(today)]
    if today_reminders:
        for r in today_reminders:
            reminder_msg += f"⏰ {r['datetime'].split()[1]} - {r['message']}\n"
    else:
        reminder_msg = "No reminders for today."

    embed = Embed(title="📊 Daily Summary", color=0x3498db)
    embed.add_field(name="🌤️ Weather", value=weather_msg, inline=False)
    embed.add_field(name="📈 Stocks", value=stock_msg, inline=False)
    embed.add_field(name="📋 Today's Tasks", value=task_msg, inline=False)
    embed.add_field(name="⏰ Today's Reminders", value=reminder_msg, inline=False)
    
    await channel.send(embed=embed)

@tasks.loop(hours=8)
async def send_status_panel():
    """Send the status panel every 8 hours."""
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        embed = Embed(title="🤖 Personal Assistant Control Panel", 
                      description="Use the buttons below to quickly access different features!", 
                      color=0x3498db)
        view = MainControlPanel()
        await channel.send(embed=embed, view=view)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    print(f'Bot ID: {bot.user.id}')
    print(f'Servers: {len(bot.guilds)}')
    
    # Start background tasks
    stock_price_check.start()
    check_reminders.start()
    send_status_panel.start()
    
    # Send initial status panel
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        embed = Embed(title="🤖 Bot Online!", 
                      description="Personal Assistant is now ready to help!", 
                      color=0x2ecc71)
        view = MainControlPanel()
        await channel.send(embed=embed, view=view)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Use `!status` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: {error.param}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument provided.")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        print(f"Error: {error}")

# Run the bot
bot.run('MTM5MjkyMDkwMzI5NzI2OTkyMw.GkF8G7.X4Nhcv3R7aeLmgbX4a7ip-rLIN-2AqKuOxWSAE')