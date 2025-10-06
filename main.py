import os
import json
import subprocess
import sys
from typing import Literal

def install_requirements():
    if os.path.exists("requirements.txt"):
        print("Installing requirements")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    else:
        with open("requirements.txt", "w", encoding="utf-8") as f:
            f.write("discord.py\n")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

install_requirements()

import discord
from discord import app_commands
from discord.ext import commands

CONFIG_PATH = "config.json"
STATE_PATH = "counts_state.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        cfg = {"token": "YOUR_BOT_TOKEN_HERE", "channels": []}
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return cfg
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)

def is_valid_binary(s: str):
    return s and all(ch in "01" for ch in s) and len(s) <= 16

def bin_to_int(s: str):
    return int(s, 2)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True

config = load_config()
state = load_state()

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

    config = load_config()
    channel_id = str(channel.id)

    if action == "add":
        if channel_id in config.get("channels", []):
            await interaction.response.send_message(f"{channel.mention} is already in the list.", ephemeral=True)
            return
        config["channels"].append(channel_id)
        save_config(config)
        await interaction.response.send_message(f"Added {channel.mention} to counting channels.")
    else:
        if channel_id not in config.get("channels", []):
            await interaction.response.send_message(f"{channel.mention} is not in the list.", ephemeral=True)
            return
        config["channels"].remove(channel_id)
        save_config(config)

        state = load_state()
        if channel_id in state:
            del state[channel_id]
            save_state(state)

        await interaction.response.send_message(f"Removed {channel.mention} from counting channels.")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready!")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    config = load_config()
    channel_id = str(message.channel.id)
    if channel_id not in config.get("channels", []):
        return

    content = message.content.strip()
    if not is_valid_binary(content):
        state = load_state()
        ch_state = state.get(channel_id, {"active": False})
        if ch_state.get("active"):
            state[channel_id] = {"active": False, "next": 1}
            save_state(state)
            await message.channel.send("Counting failed!")
        return

    val = bin_to_int(content)
    state = load_state()
    ch_state = state.get(channel_id)

    if not ch_state or not ch_state.get("active"):
        if val == 1:
            state[channel_id] = {"active": True, "next": 2}
            save_state(state)
            await message.channel.send("Counting started!")
        return

    expected = ch_state["next"]
    if val == expected:
        next_expected = expected + 1
        if next_expected > 2**16 - 1:
            state[channel_id] = {"active": False, "next": 1}
            save_state(state)
            await message.channel.send("Counting complete (max 16-bit reached). Resetting!")
        else:
            state[channel_id]["next"] = next_expected
            save_state(state)
    else:
        state[channel_id] = {"active": False, "next": 1}
        save_state(state)
        await message.channel.send("Counting failed!")

if __name__ == "__main__":
    cfg = load_config()
    token = cfg.get("token")
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please add your bot token in config.json first.")
        sys.exit(1)
    bot.run(token)
