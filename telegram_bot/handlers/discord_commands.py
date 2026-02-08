import asyncio

from utils.logger import logger
from discord_bot.senders import send_embed_to_discord, send_reply_embed_to_discord
from telegram_bot.bot import bot
from telegram_bot.tg_utils.avatar import get_user_avatar
from telebot.types import Message
from discord_bot.bot import get_discord_loop
from io import BytesIO
from discord_bot.ds_utils.ds_online_info import get_active_channels, get_online_info
from telegram_bot.tg_utils.reaction import send_react
from discord_bot.ds_utils.invite_with_role import get_invite_link
from utils.mini_utils import run_in_thread
from telebot import types 

pending_requests = {}

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def get_pending_requests():
    return pending_requests

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def pop_pending_requests(key): 
    pending_requests.pop(key)
 

@bot.message_handler(
    content_types=['text'],
    commands=["tts",'ттс']
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def tts_handler(message: Message):
    text_to_say = message.text.replace('/tts', '').strip()
    if not text_to_say:
        bot_msg=bot.reply_to(message, "Извинись, неправильно")
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                  ,time_sleep=5)
        return
    text_to_say = f"{(message.from_user.username or message.from_user.first_name or 'NoName')} передал {text_to_say}"
    #ds list
    future = asyncio.run_coroutine_threadsafe(
        get_active_channels(),
        get_discord_loop()
    )
    try:
        channels = future.result(timeout=5)
    except Exception:
        bot_msg=bot.reply_to(message, "Дискорд накрылся, извинись")
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                  ,time_sleep=5)
        return 
    if not channels:
        bot_msg=bot.reply_to(message, "🔇 В Discord сейчас никого нет в голосовых каналах.")
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                  ,time_sleep=5)
        return
    
    markup = types.InlineKeyboardMarkup()
    for ch in channels:
        callback_data = f"tts|{ch['id']}"
        markup.add(types.InlineKeyboardButton(text=ch['name'], callback_data=callback_data))
    
    bot_msg = bot.send_message(
        message.chat.id, 
        f"Выбери канал для озвучки текста: \n\"{text_to_say}\"", 
        reply_markup=markup
    ) 
    pending_requests[bot_msg.message_id] = {
        'text': text_to_say,
        'user_id': message.from_user.id
    }
    run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                  ,time_sleep=5)
    run_in_thread(pop_pending_requests, bot_msg.message_id, time_sleep=5)
    

@bot.message_handler(
    content_types=['text','photo'],
    func=lambda m: (m.text or m.caption or "").startswith(("/2ds", "/2дс"))
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def to_ds_handler(message: Message):
    to_ds(message)

@bot.message_handler(
    content_types=['text'],
    commands=['dsinfo','дсинфо'],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def ds_info_handler(message: Message):
    ds_info(message)

@bot.message_handler(
    content_types=['text'],
    commands=['invite','приглашение'],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def invite_handler(message: Message):
    invite(message)















@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
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


@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def ds_info(message:Message):
    res = asyncio.run_coroutine_threadsafe(
        get_online_info()
        ,get_discord_loop()
    ).result()
    bot.reply_to(message,res, parse_mode="Markdown")
    send_react(message.chat.id, message.message_id)

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def to_ds(message:Message):
    if not message.reply_to_message:
        bot.reply_to(message, "Еблан, ты хоть выдели, что пересылаешь")
        return
    kwargs = {
        "sender" : message.from_user.username,
        "senderlink" : f"https://t.me/{message.from_user.username}" if message.from_user.username else message.from_user.id,
        "text" : message.reply_to_message.text if message.reply_to_message.content_type=='text' else (message.reply_to_message.caption or " "),
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


@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def invite(message: Message):
    res = asyncio.run_coroutine_threadsafe(
        get_invite_link()
        , get_discord_loop()
    ).result()
    bot.reply_to(message, res, parse_mode="Markdown")
    send_react(message.chat.id, message.message_id)