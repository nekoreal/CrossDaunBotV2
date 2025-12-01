from discord.ext import commands
import discord
from config import DISCORD_TOKEN
from .handlers import register_handlers
from .senders import get_bot
import asyncio
from utils.logger import logger

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.messages = True
intents.message_content = True

discord_loop: None | asyncio.AbstractEventLoop = None

bot = commands.Bot(command_prefix='/', intents=intents)
register_handlers(bot)
get_bot(bot)


@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
@bot.event
async def on_ready():
    global discord_loop
    discord_loop = bot.loop
    print("Discord loop initialized!")
def get_discord_loop():
    return bot.loop

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
async def run_discord_bot():
    await bot.start(DISCORD_TOKEN)
    await asyncio.sleep(5)

