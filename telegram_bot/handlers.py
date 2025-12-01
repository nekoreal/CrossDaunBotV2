import asyncio
from utils.logger import logger
from discord_bot.senders import send_embed_to_discord
from .bot import bot
from .tg_utils.avatar import get_user_avatar


@bot.message_handler(commands=['ds'])
def handle_ds(message):
    print(message.from_user.id)
    print(message.content)
    if message.from_user.id == bot.user.id:
        return
    print(message.content)
    senderlink = f"https://t.me/{message.from_user.username}" if message.from_user.username else message.from_user.id
    asyncio.run(send_embed_to_discord(
        sender=message.from_user.username,
        senderlink=senderlink,
        message=message.content,
        senderavatar=get_user_avatar(bot, message.from_user.id)
    ))