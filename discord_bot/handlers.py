from discord.ext import commands
from utils.logger import logger
from .senders import send_embed_to_discord
import requests
from telegram_bot.senders import send_telegram_message

bot: commands.Bot | None  = None

def register_handlers(local_bot: commands.Bot ):
    global bot
    bot = local_bot

    bot.event(on_ready)
    bot.add_command(tg)

@logger(
    txtfile="discord_bot.txt",
    print_log=True,
    time_log=True,
)
async def on_ready():
    print("ds_bot_started")


@commands.command(name="tg")
async def tg(ctx):
    if ctx.message.author.bot:
        return
    message_text = ctx.message.content[4:].strip()
    author = ctx.message.author
    if message_text:
        send_telegram_message(author, message_text)

    for attachment in ctx.message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            ...
            # Скачиваем фото
            photo_bytes = requests.get(attachment.url).content
            #telegram_bot.send_photo(TELEGRAM_CHAT_ID, photo=photo_bytes, caption=message_text)
@tg.error
async def tg_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send(f"Хуесос без роли telegram, {ctx.author}")
