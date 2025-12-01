from discord.ext import commands
from utils.logger import logger
from .senders import send_embed_to_discord
import requests
from telegram_bot.senders import send_telegram_message, send_telegram_photo


bot: commands.Bot | None  = None

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def register_handlers(local_bot: commands.Bot ):
    global bot
    bot = local_bot

    bot.add_command(tg)



@commands.command(name="tg")
@commands.has_role("telegram")
async def tg(ctx):
    if ctx.message.author.bot:
        return
    message_text = ctx.message.content[4:].strip()
    author = ctx.message.author
    if message_text:
        send_telegram_message(author, message_text)

    for attachment in ctx.message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            photo_bytes = requests.get(attachment.url).content
            send_telegram_photo(author, photo_bytes)
    await ctx.message.add_reaction('✅')
@tg.error
async def tg_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.message.add_reaction('❌')
