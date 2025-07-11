import discord
from discord.ext import commands, tasks
from mcstatus import JavaServer
from mcrcon import MCRcon
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium import webdriver
import os
import asyncio
from discord.ui import View, Button
import time
import re
from discord.ui import View, Button, Modal, TextInput
from functools import partial
from discord.ext.commands import Context
from datetime import datetime
import aiofiles
from pathlib import Path
from pathlib import Path
import subprocess

intents = discord.Intents.default()
intents.message_content = True  # Enables command recognition
bot = commands.Bot(command_prefix='!', intents=intents)

TOKEN = 'MTM4MDE5NzE4NzkyNDkxODM3Mw.G6tTKI.FZHk1QnEqBuGd3dtES-O3pdKGXvV04kzbHNXu4'
RCON_PASSWORD = "2dayisM0nday@2"
SERVER_IP = '140.238.156.90'
SERVER_PORT = 25565
YOUR_CHANNEL_ID = 1382447521531433150  # Replace with actual channel ID
# Add this configuration near your other constants
MINECRAFT_LOG_PATH = "/mnt/minecraft-data/minecraft/logs/latest.log"  # Adjust path as needed
CHAT_CHANNEL_ID = 1382447521531433150  # Channel for chat messages (can be same as status channel)

RCON_HOST = "140.238.156.90"
RCON_PORT = 25575
user_cooldowns = {}

# Enhanced say command that shows it came from Discord
@bot.command()
async def say(ctx, *, message):
    """Send a broadcast message to all players in the server"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            # Include Discord username in the message
            formatted_message = f"[Discord - {ctx.author.display_name}] {message}"
            mcr.command(f"say {formatted_message}")
            await ctx.send(f"📢 Sent to Minecraft chat:\n> {message}")
    except Exception as e:
        await ctx.send(f"❌ Failed to broadcast message: {e}")

class CustomCommandModal(Modal, title="Execute Custom Command"):
    def __init__(self):
        super().__init__()

    command = TextInput(
        label="Minecraft Command",
        placeholder="Enter your RCON command here (e.g., time set day, weather clear)",
        style=discord.TextStyle.short,
        max_length=200,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
                response = mcr.command(str(self.command))
                await interaction.response.send_message(f"✅ Command executed: `{self.command}`\n```{response}```")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to run command: {e}")

class MapView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="🖼 Get Snapshot", style=discord.ButtonStyle.primary, custom_id="get_snapshot"))

class CommandPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="📡 Status", style=discord.ButtonStyle.primary, custom_id="auto_status")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "status")
    
    @discord.ui.button(label="👥 Players", style=discord.ButtonStyle.primary, custom_id="auto_players")
    async def players_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "players")
    
    @discord.ui.button(label="🔌 Plugins", style=discord.ButtonStyle.primary, custom_id="auto_plugins")
    async def plugins_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "plugins")
    
    @discord.ui.button(label="🌍 Worlds", style=discord.ButtonStyle.primary, custom_id="auto_worlds")
    async def worlds_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "worlds")
    
    @discord.ui.button(label="📈 TPS", style=discord.ButtonStyle.primary, custom_id="auto_tps")
    async def tps_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "tps")
    
    @discord.ui.button(label="🌱 Seed", style=discord.ButtonStyle.primary, custom_id="auto_seed")
    async def seed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "seed")
    
    @discord.ui.button(label="🗺️ Map", style=discord.ButtonStyle.primary, custom_id="auto_map")
    async def map_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "map")
    
    @discord.ui.button(label="🧮 SizeWorld", style=discord.ButtonStyle.primary, custom_id="auto_sizeworld")
    async def sizeworld_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "sizeworld")
    
    @discord.ui.button(label="🧮 SizeMap", style=discord.ButtonStyle.primary, custom_id="auto_sizemap")
    async def sizemap_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "sizemap")
    
    @discord.ui.button(label="💬 HowTo", style=discord.ButtonStyle.primary, custom_id="auto_howto")
    async def howto_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "howto")
    
    @discord.ui.button(label="📁 SizeMine", style=discord.ButtonStyle.primary, custom_id="auto_sizemine")
    async def sizemine_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "sizemine")
    
    @discord.ui.button(label="⚡ Custom Command", style=discord.ButtonStyle.secondary, custom_id="custom_command")
    async def custom_command_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_custom_command(interaction)
    
    @discord.ui.button(label="📋 Projects", style=discord.ButtonStyle.primary, custom_id="auto_projects")
    async def projects_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_command(interaction, "projects")

    async def handle_custom_command(self, interaction: discord.Interaction):
        """Handle custom command input via modal"""
        modal = CustomCommandModal()
        await interaction.response.send_modal(modal)

    async def handle_command(self, interaction: discord.Interaction, command_name: str):
        await interaction.response.defer()

        ctx = await bot.get_context(interaction.message)

        # Run the command using the bot's built-in invoke mechanism
        cmd = bot.get_command(command_name)
        if cmd:
            ctx.command = cmd
            try:
                await bot.invoke(ctx)  # This handles Cogs properly
            except Exception as e:
                await interaction.followup.send(f"❌ Error executing command: {str(e)}")
        else:
            await interaction.followup.send(f"❌ Command '{command_name}' not found.")
        
        # Create a mock context for the command
        class MockContext:
            def __init__(self, interaction):
                self.interaction = interaction
                self.author = interaction.user
                self.channel = interaction.channel
                self.guild = interaction.guild
                self.bot = bot
                
            async def send(self, *args, **kwargs):
                await self.interaction.followup.send(*args, **kwargs)
        
        ctx = MockContext(interaction)
        
        # Get and invoke the command
        cmd = bot.get_command(command_name)
        if cmd:
            try:
                # Call the command callback with just the context (no cog since these are standalone commands)
                await cmd.callback(ctx)
            except Exception as e:
                await interaction.followup.send(f"❌ Error executing command: {str(e)}")
        else:
            await interaction.followup.send(f"❌ Command '{command_name}' not found.")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return  # Only handle component interactions (buttons, selects)

    custom_id = interaction.data.get("custom_id")
    if not custom_id:
        return

    user_id = interaction.user.id
    now = time.time()

    # Handle snapshot button with cooldown
    if custom_id == "get_snapshot":
        if user_id in user_cooldowns:
            elapsed = now - user_cooldowns[user_id]
            if elapsed < 120:
                remaining = int(120 - elapsed)
                await interaction.response.send_message(
                    f"🕒 You're on cooldown! Try again in {remaining} seconds.",
                    ephemeral=True
                )
                return

        user_cooldowns[user_id] = now
        await interaction.response.defer(thinking=True)

        try:
            url = "http://140.238.156.90:8123"
            options = Options()
            options.headless = True
            options.add_argument("--width=1280")
            options.add_argument("--height=720")
            service = Service('/usr/local/bin/geckodriver')

            driver = webdriver.Firefox(service=service, options=options)
            driver.set_window_size(1280, 720)
            driver.get(url)
            await asyncio.sleep(5)

            screenshot_path = "/tmp/dynmap_snapshot.png"
            driver.save_screenshot(screenshot_path)
            driver.quit()

            file = discord.File(screenshot_path, filename="dynmap.png")
            await interaction.followup.send("🖼 Snapshot of Dynmap:", file=file)

            os.remove(screenshot_path)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to take snapshot:\n```{e}```")
        return

@bot.command()
async def command(ctx, *, cmd):
    """Execute a Minecraft command via RCON"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = mcr.command(cmd)
            await ctx.send(f"✅ Command executed:\n```{response}```")
    except Exception as e:
        await ctx.send(f"❌ Failed to run command: {e}")

def strip_minecraft_colors(text):
    """Remove Minecraft color/formatting codes (e.g., §a, §6, §x§e§d...)"""
    return re.sub(r'§[0-9a-fklmnorx]|§x(?:§[0-9a-f]){6}', '', text, flags=re.IGNORECASE)

@bot.command()
async def status(ctx):
    """Simplified Minecraft server status"""
    try:
        server = JavaServer.lookup(f"{SERVER_IP}:{SERVER_PORT}")
        status = server.status()

        embed = discord.Embed(
            title="Oracle Minecraft Server Status",
            description="Running on Oracle VM with Ampere architecture, 16gb ram and 100gb dedictaed storage",
            color=discord.Color.green()
        )
        embed.add_field(name="📡 IP", value=SERVER_IP, inline=False)
        embed.add_field(name="🟢 Status", value="Online", inline=True)
        embed.add_field(name="📶 Ping", value=f"{status.latency:.0f} ms", inline=True)
        embed.add_field(name="👥 Players", value=f"{status.players.online}/{status.players.max}", inline=True)

        if status.players.sample:
            names = ', '.join([player.name for player in status.players.sample])
            embed.add_field(name="🎮 Online Players", value=names, inline=False)

        await ctx.send(embed=embed)

    except Exception as e:
        embed = discord.Embed(
            title="The stat is the strat ya baka",
            color=discord.Color.red(),
            description=f"🔴 Server is offline or unreachable.\n```{e}```"
        )
        await ctx.send(embed=embed)

@bot.command()
async def players(ctx):
    """List all currently online players (if visible to the query)"""
    try:
        server = JavaServer.lookup(f"{SERVER_IP}:{SERVER_PORT}")
        status = server.status()
        if status.players.sample:
            names = ', '.join([player.name for player in status.players.sample])
            await ctx.send(f"👥 Online players: {names}")
        else:
            await ctx.send("👥 No players currently visible.")
    except:
        await ctx.send("❌ Unable to fetch player list.")

@bot.command()
async def plugins(ctx):
    """List installed plugins with cleaned formatting"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = strip_minecraft_colors(mcr.command("plugins")).strip()

            if "Plugins (" in response:
                plugin_list = response.split("):", 1)[-1].strip()
            else:
                plugin_list = response

            await ctx.send(f"🔌 **Plugins Installed:**\n`{plugin_list}`")
    except Exception as e:
        await ctx.send(f"❌ Failed to fetch plugins: {e}")

@bot.command()
async def worlds(ctx):
    """List loaded worlds with formatting cleaned"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = strip_minecraft_colors(mcr.command("mv list")).strip()

            # Remove header/footer if present
            cleaned_lines = [
                line for line in response.splitlines()
                if not line.startswith("====") and line.strip()
            ]
            worlds_text = '\n'.join(cleaned_lines)

            await ctx.send(f"🌍 **Worlds Loaded:**\n```{worlds_text}```")
    except Exception as e:
        await ctx.send(f"❌ Failed to fetch world list: {e}")

@bot.command()
async def tps(ctx):
    """Check server TPS (ticks per second)"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = strip_minecraft_colors(mcr.command("tps")).strip()
            await ctx.send(f"📈 **TPS Status:**\n```{response}```")
    except Exception as e:
        await ctx.send(f"❌ Failed to fetch TPS: {e}")

@bot.command()
async def seed(ctx):
    """Get the current world's seed"""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            response = strip_minecraft_colors(mcr.command("seed")).strip()
            await ctx.send(f"🌱 Seed: `{response.strip()}`")
    except Exception as e:
        await ctx.send(f"❌ Failed to get seed: {e}")

@bot.command()
async def ip(ctx):
    """Displays the Minecraft server IP address."""
    await ctx.send(f"📡 Server IP: `{SERVER_IP}`")

@bot.command()
async def map(ctx):
    """Share Dynmap link with snapshot button."""
    dynmap_url = "http://140.238.156.90:8123"
    embed = discord.Embed(
        title="🗺️ Live Dynmap",
        description="Click below to open the live map or request a current snapshot.",
        color=discord.Color.green()
    )
    embed.add_field(name="🌐 Map Link", value=f"[Open Dynmap]({dynmap_url})", inline=False)
    await ctx.send(embed=embed, view=MapView())

@bot.command()
async def sizeworld(ctx):
    """Return the size of multiple Minecraft world folders and the total."""
    world_paths = {
    	"World": "/mnt/minecraft-data/minecraft/world",
        "Ganatcho": "/mnt/minecraft-data/minecraft/Ganatcho",
        "PixlP": "/mnt/minecraft-data/minecraft/PixlP",
        "Sanctuary": "/mnt/minecraft-data/minecraft/Sanctuary",
        "Mordor": "/mnt/minecraft-data/minecraft/Mordor",
        "Nether": "/mnt/minecraft-data/minecraft/world_nether",
        "The End": "/mnt/minecraft-data/minecraft/world_the_end"
    }

    total_bytes = 0
    results = []

    for name, path in world_paths.items():
        proc = await asyncio.create_subprocess_shell(
            f"du -sb {path}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            size_bytes = int(stdout.decode().split()[0])
            total_bytes += size_bytes
            size_gb = size_bytes / (1024 ** 3)
            results.append(f"📁 **{name}**: `{size_gb:.2f} GB`")
        else:
            results.append(f"❌ **{name}**: Error - `{stderr.decode().strip()}`")

    total_gb = total_bytes / (1024 ** 3)
    results.append(f"\n📦 **Total World Size**: `{total_gb:.2f} GB`")

    await ctx.send("🌍 **World Folder Sizes:**\n" + "\n".join(results))

@bot.command()
async def sizemine(ctx):
    """Return the size of the minecraft folder."""
    map_path = "/mnt/minecraft-data/minecraft"  # adjust if needed
    proc = await asyncio.create_subprocess_shell(
        f"du -sh {map_path}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode == 0:
        size = stdout.decode().strip()
        await ctx.send(f"Minecraft folder size:\n```{size}```")
    else:
        await ctx.send(f"❌ Error getting size:\n```{stderr.decode().strip()}```")

@bot.command()
async def panel(ctx):
    """Shows interactive command buttons"""
    embed = discord.Embed(
        title="🎮 Minecraft Server Command Panel",
        description="Click a button below to run the command without typing!",
        color=discord.Color.teal()
    )
    await ctx.send(embed=embed, view=CommandPanel())

@bot.command()
async def sizemap(ctx):
    """Return the size of the Dynmap folder."""
    map_path = "/mnt/minecraft-data/minecraft/plugins/dynmap"  # adjust if needed
    proc = await asyncio.create_subprocess_shell(
        f"du -sh {map_path}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode == 0:
        size = stdout.decode().strip()
        await ctx.send(f"🗺️ Dynmap tiles folder size:\n```{size}```")
    else:
        await ctx.send(f"❌ Error getting map size:\n```{stderr.decode().strip()}```")

@bot.command()
async def howto(ctx):
    """List all available bot commands with usage examples"""
    embed = discord.Embed(
        title="🛠 Bot Commands",
        description="Here are the available commands and what they do:",
        color=discord.Color.blurple()
    )

    embed.add_field(name="`!status`", value="Shows server status, player count, ping, and who's online.", inline=False)
    embed.add_field(name="`!players`", value="Lists currently online players.", inline=False)
    embed.add_field(name="`!plugins`", value="Lists all installed plugins (via RCON).", inline=False)
    embed.add_field(name="`!worlds`", value="Lists all loaded worlds (requires Multiverse).", inline=False)
    embed.add_field(name="`!tps`", value="Shows current server TPS (performance metric).", inline=False)
    embed.add_field(name="`!ip`", value="Shows the Minecraft server IP address.", inline=False)
    embed.add_field(name="`!map`", value="Sends a live screenshot of the Dynmap web view.", inline=False)
    embed.add_field(name="`!seed`", value="Displays the current world's seed.", inline=False)
    embed.add_field(name="`!say <message>`", value="Broadcasts a message to all players.\nExample: `!say Hello world!`", inline=False)
    embed.add_field(name="`!command <rcon_command>`", value="Executes any RCON command directly.\nExample: `!command time set day`", inline=False)
    embed.add_field(name="`!sizeworld`", value="Shows sizes of major world folders (`Ganatcho`, `PixlP`, `Sanctuary`, `Mordor`, `Nether`, `End`) with total.", inline=False)
    embed.add_field(name="`!sizemap`", value="Shows the size of the Dynmap tile folder.", inline=False)
    embed.add_field(name="`!howto`", value="Displays this command reference guide.", inline=False)

    await ctx.send(embed=embed)

@tasks.loop(minutes=360)
async def check_server_status():
    await bot.wait_until_ready()
    channel = bot.get_channel(YOUR_CHANNEL_ID)
    if not channel:
        print("❌ Channel not found.")
        return

    try:
        # Get server status first
        server = JavaServer.lookup(f"{SERVER_IP}:{SERVER_PORT}")
        status = server.status()
        
        # Create status embed
        status_embed = discord.Embed(
            title="🕐 6 Hour Server Check",
            color=discord.Color.green()
        )
        status_embed.add_field(name="🟢 Status", value="Online", inline=True)
        status_embed.add_field(name="👥 Players", value=f"{status.players.online}/{status.players.max}", inline=True)
        status_embed.add_field(name="📶 Ping", value=f"{status.latency:.0f} ms", inline=True)
        
        if status.players.sample:
            names = ', '.join([player.name for player in status.players.sample])
            status_embed.add_field(name="🎮 Online Players", value=names, inline=False)
        
        # Send status message
        await channel.send(embed=status_embed)
        
    except Exception as e:
        # Server is offline
        status_embed = discord.Embed(
            title="🕐 90-Minute Server Check",
            color=discord.Color.red(),
            description=f"🔴 Server is offline or unreachable.\n```{e}```"
        )
        await channel.send(embed=status_embed)
    
    # Always send the command panel after status
    panel_embed = discord.Embed(
        title="🎮 Minecraft Server Command Panel",
        description="Click a button below to run the command without typing!",
        color=discord.Color.teal()
    )
    await channel.send(embed=panel_embed, view=CommandPanel())

# Load the project board cog
async def load_cogs():
    try:
        await bot.load_extension('project_board')
        print("✅ Project Board cog loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load Project Board cog: {e}")

# Main function to run the bot
async def main():
    await load_cogs()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())