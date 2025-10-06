import os
import json
import subprocess
import sys
from typing import Literal

def ensure_requirements():
    if not os.path.exists("requirements.txt"):
        with open("requirements.txt", "w", encoding="utf-8") as f:
            f.write("discord.py\n")
    print("Installing requirements...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

ensure_requirements()

import discord
from discord import app_commands
from discord.ext import commands

CONFIG_FILE = "config.json"
STATE_FILE = "counts_state.json"

def get_config():
    if not os.path.exists(CONFIG_FILE):
        default = {"token": "YOUR_BOT_TOKEN_HERE", "channels": []}
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2)
        return default
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def get_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)

def looks_like_binary(s):
    return s and all(c in "01" for c in s) and len(s) <= 16

def binary_to_int(s):
    return int(s, 2)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

config = get_config()
state = get_state()

class CountingBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced.")

bot = CountingBot()

@bot.tree.command(name="countchannel", description="Add or remove counting channel (mods only).")
@app_commands.describe(action="add or remove", channel="Channel to add or remove.")
async def countchannel(interaction: discord.Interaction, action: Literal["add", "remove"], channel: discord.TextChannel):
    perms = interaction.user.guild_permissions
    if not (perms.manage_messages or perms.administrator):
        await interaction.response.send_message("You need Manage Messages or Administrator permission.", ephemeral=True)
        return

    config = get_config()
    cid = str(channel.id)

    if action == "add":
        if cid in config.get("channels", []):
            await interaction.response.send_message(f"{channel.mention} is already in the list.", ephemeral=True)
            return
        config["channels"].append(cid)
        save_config(config)
        await interaction.response.send_message(f"Added {channel.mention} to counting channels.")
    else:
        if cid not in config.get("channels", []):
            await interaction.response.send_message(f"{channel.mention} is not in the list.", ephemeral=True)
            return
        config["channels"].remove(cid)
        save_config(config)

        state = get_state()
        if cid in state:
            del state[cid]
            save_state(state)

        await interaction.response.send_message(f"Removed {channel.mention} from counting channels.")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready!")

@bot.event
async def on_message(msg: discord.Message):
    if msg.author.bot or not msg.guild:
        return

    config = get_config()
    cid = str(msg.channel.id)
    if cid not in config.get("channels", []):
        return

    text = msg.content.strip()
    if not looks_like_binary(text):
        state = get_state()
        ch = state.get(cid, {"active": False})
        if ch.get("active"):
            state[cid] = {"active": False, "next": 1}
            save_state(state)
            await msg.channel.send("Counting failed!")
        return

    value = binary_to_int(text)
    state = get_state()
    ch = state.get(cid)

    if not ch or not ch.get("active"):
        if value == 1:
            state[cid] = {"active": True, "next": 2}
            save_state(state)
            await msg.channel.send("Counting started!")
            await msg.add_reaction("✅")
        return

    expected = ch["next"]
    if value == expected:
        next_val = expected + 1
        if next_val > 2**16 - 1:
            state[cid] = {"active": False, "next": 1}
            save_state(state)
            await msg.channel.send("Counting complete (max 16-bit reached). Resetting!")
        else:
            state[cid]["next"] = next_val
            save_state(state)
        await msg.add_reaction("✅")
    else:
        state[cid] = {"active": False, "next": 1}
        save_state(state)
        await msg.channel.send("Counting failed!")

if __name__ == "__main__":
    cfg = get_config()
    token = cfg.get("token")
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please add your bot token in config.json first.")
        sys.exit(1)
    bot.run(token)