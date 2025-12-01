import asyncio
from utils.logger import logger
from discord_bot.senders import send_embed_to_discord, send_reply_embed_to_discord
from .bot import bot
from .tg_utils.avatar import get_user_avatar
from telebot.types import Message
from discord_bot.bot import get_discord_loop
from io import BytesIO
from discord_bot.ds_utils.ds_online_info import get_online_info
from random import randint
from .tg_utils.reaction import send_react,send_react_for_user
import threading
from utils.model_gpt import dialoggpt, askgpt

@bot.message_handler(content_types=['photo','text'])
@logger(
    txtfile="telegram_bot.log",
    print_log=True,
    only_exc=True,
    time_log=True,
    raise_exc=False
)
def handle_ds(message:Message):
    text = message.text if message.content_type == 'text' else message.caption
    if message.from_user.id == bot.user.id:
        return
    if text.startswith("/ds ") or text.startswith("/дс "):
        ds(message)
        return
    elif text.startswith("/2ds") or text.startswith("/2дс"):
        to_ds(message)
        return
    elif text.startswith("/dsinfo") or text.startswith("/дсинфо"):
        dsinfo(message)
        return
    elif text.startswith("/n") or text.startswith("/н"):
        bot.reply_to(message, askgpt(message.text[2:]))
        send_react(message.chat.id, message.message_id)
        return

    send_react_for_user(message.chat.id, message.message_id, message.from_user.id)
    if len(message.text)>25:
        if randint(0,17)==7:
            try:
                threading.Thread(target=bot.reply_to, args=(message,dialoggpt(message.text, message.from_user.username),)).start()
                return
            except:
                pass



def dsinfo(message:Message):
    res = asyncio.run_coroutine_threadsafe(
        get_online_info()
        ,get_discord_loop()
    ).result()
    bot.reply_to(message,res, parse_mode="Markdown")
    send_react(message.chat.id, message.message_id)

def ds(message:Message):
    kwargs = {
        "sender" : message.from_user.username,
        "senderlink" : f"https://t.me/{message.from_user.username}" if message.from_user.username else message.from_user.id,
        "text" : message.text[3:] if message.content_type=='text' else message.caption[3:],
        "senderavatar" : get_user_avatar(bot, message.from_user.id)
    }
    if message.content_type=='photo' :
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        photo_bytes = BytesIO(bot.download_file(file_info.file_path))
        kwargs.update({"photo":photo_bytes})
    asyncio.run_coroutine_threadsafe(
        send_embed_to_discord(  **kwargs  ),
        get_discord_loop()
    )
    send_react(message.chat.id, message.message_id)

def to_ds(message:Message):
    if not message.reply_to_message:
        bot.reply_to(message, "Еблан, ты хоть выдели, что пересылаешь")
        return
    kwargs = {
        "sender" : message.from_user.username,
        "senderlink" : f"https://t.me/{message.from_user.username}" if message.from_user.username else message.from_user.id,
        "text" : message.reply_to_message.text if message.reply_to_message.content_type=='text' else message.reply_to_message.caption,
        "senderavatar" : get_user_avatar(bot, message.from_user.id),
        "rsender": message.reply_to_message.from_user.username,
        "rsenderavatar": get_user_avatar(bot, message.reply_to_message.from_user.id),
    }
    if message.reply_to_message.content_type=='photo' :
        file_id = message.reply_to_message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        photo_bytes = BytesIO(bot.download_file(file_info.file_path))
        kwargs.update({"photo":photo_bytes})
    asyncio.run_coroutine_threadsafe(
        send_reply_embed_to_discord(  **kwargs  ),
        get_discord_loop()
    )
    send_react(message.chat.id, message.message_id)