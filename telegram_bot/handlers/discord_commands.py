import asyncio

from utils.logger import logger
from discord_bot.senders import send_embed_to_discord, send_reply_embed_to_discord
from telegram_bot.bot import bot
from telegram_bot.tg_utils.avatar import get_user_avatar
from telebot.types import Message
from discord_bot.bot import get_discord_loop
from io import BytesIO
from discord_bot.ds_utils.ds_online_info import get_online_info
from telegram_bot.tg_utils.reaction import send_react
from discord_bot.ds_utils.invite_with_role import get_invite_link

@bot.message_handler(
    content_types=['text','photo'],
    func=lambda m: (m.text or m.caption or "").startswith(("/ds ", "/дс ")) or (m.text or m.caption or "") in ["/ds", "/дс"]
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def ds_handler(message: Message):
    ds(message)

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