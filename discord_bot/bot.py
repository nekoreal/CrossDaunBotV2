from discord.ext import commands
import discord
from config import DISCORD_TOKEN
from .handlers import register_handlers
from .senders import get_bot

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)
register_handlers(bot)
get_bot(bot)

async def run_discord_bot():
    await bot.start(DISCORD_TOKEN)
