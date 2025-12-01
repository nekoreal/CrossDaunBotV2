from discord.ext import commands
import discord
from config import DISCORD_TOKEN
from .handlers import register_handlers
import asyncio
from utils.logger import logger
from config import DISCORD_GUILD_ID

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.messages = True
intents.message_content = True

discord_loop: None | asyncio.AbstractEventLoop = None



bot = commands.Bot(command_prefix='/', intents=intents)
register_handlers(bot)


def get_discord_loop():
    return bot.loop
def get_bot():
    return bot

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
@bot.event
async def on_ready():
    global discord_loop, INVITES
    discord_loop = bot.loop
    print("Discord loop initialized!")
    invites = await bot.get_guild(DISCORD_GUILD_ID).invites()
    for i in invites:
        await i.delete()



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



