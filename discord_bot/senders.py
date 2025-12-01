import discord
from discord.ext import commands
from config import DISCORD_GUILD_ID, DISCORD_CHANNEL_ID
from utils.logger import logger

bot: commands.Bot | None  = None

def get_bot(local_bot: commands.Bot ):
    global bot
    bot = local_bot

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=True,
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