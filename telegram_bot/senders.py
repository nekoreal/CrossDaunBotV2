from pickle import FALSE

from rabbitmq import queue_sender
from .bot import bot
from config import TELEGRAM_CHAT_ID
from utils.logger import logger
from telebot import types 
from telegram_markdown_converter  import convert_markdown

from .tg_db.db_controllers.user_controller import get_followers


@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def send_telegram_message(author, text):
    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=convert_markdown(f"`{author}`: \n```ini\n{text}\n```"),parse_mode="MarkdownV2"
    )

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def send_telegram_photo(author, photo):
    bot.send_photo(caption=convert_markdown(f"`{author}`"), photo=photo, chat_id=TELEGRAM_CHAT_ID, parse_mode="MarkdownV2") #софа извини, я не кричу, ты не глухая, ты софа, я ебу игоря

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def send_telegram_video(author, video):
    bot.send_video(caption=convert_markdown(f"`{author}`"), video=video, chat_id=TELEGRAM_CHAT_ID, parse_mode="MarkdownV2")

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def send_verify_msg(id, username=None):
    markup = types.InlineKeyboardMarkup() 
    item_yes = types.InlineKeyboardButton("Да ✅", callback_data=f"verify|yes|{id}|{username}")
    item_no = types.InlineKeyboardButton("Нет ❌", callback_data=f"verify|no|{id}|{username}")
    markup.add(item_yes, item_no)

    msg = convert_markdown(f"🔔 В Discord зашел `{username or id}`\n\nВы можете распознать это существо?")
    bot.send_message(TELEGRAM_CHAT_ID, msg, reply_markup=markup, parse_mode="MarkdownV2")

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def send_ds_info_to_followers(info:str="Empty info"):
    followers_list = get_followers()
    if not followers_list: return
    for follower in followers_list:
        try:
            bot.send_message(follower, convert_markdown(info), parse_mode="MarkdownV2")
        except Exception as e:
            queue_sender("tg_notify",
                         type="error",
                         body={"exp": str(e), "user_id": follower}, )
























