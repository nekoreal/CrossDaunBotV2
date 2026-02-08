import asyncio
import discord
from discord.ext import commands
from config import DISCORD_GUILD_ID, DISCORD_CHANNEL_ID
from utils.logger import logger
from .bot import get_bot 

bot: commands.Bot | None  = get_bot()

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def get_bot(local_bot: commands.Bot ):
    global bot
    bot = local_bot

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
async def send_embed_to_discord(
        sender="Unknown",
        text=None,
        senderavatar=None,
        senderlink=None,
        photo=None
):

    embed = discord.Embed(
        color=0x0088ff
    )
    files = []
    if text : embed.description = text
    if senderavatar :
        files.append(discord.File(senderavatar, filename="senderavatar.jpg"))
        embed.set_author(name = sender, url=senderlink , icon_url="attachment://senderavatar.jpg")
    else: embed.set_author(name = sender, url=senderlink)
    if photo:
        files.append(discord.File(photo, filename="photo.jpg"))
        embed.set_image(url="attachment://photo.jpg")
    await bot.get_channel(DISCORD_CHANNEL_ID).send(embed=embed, files=files)

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
async def send_reply_embed_to_discord(
        sender="Unknown",
        text=None,
        senderavatar=None,
        senderlink=None,
        rsender=None,
        rsenderavatar=None,
        photo=None
):
    embed = discord.Embed(
        color=0x2288ff
    )
    files = []
    if senderavatar :
        files.append(discord.File(senderavatar, filename="senderavatar.jpg"))
        embed.set_author(name=f"{sender} переслал:"  , url=senderlink , icon_url="attachment://senderavatar.jpg")
    else: embed.set_author(name=f"{sender} переслал:"  , url=senderlink )
    if rsenderavatar:
        files.append(discord.File(rsenderavatar, filename="rsenderavatar.jpg"))
        embed.set_footer(text=f"{rsender}: {text}", icon_url="attachment://rsenderavatar.jpg")
    else: embed.set_footer(text=f"{rsender}: {text}")
    if photo:
        files.append(discord.File(photo, filename="photo.jpg"))
        embed.set_image(url="attachment://photo.jpg")
    await bot.get_channel(DISCORD_CHANNEL_ID).send(embed=embed, files=files)

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
async def send_tts(channel_id, text): 
    voice_channel = bot.get_channel(channel_id)  
    if voice_channel:
        msg = await voice_channel.send(f"{text}", tts=True)
        await asyncio.sleep(10)
        await msg.delete() 
        return True
    return False