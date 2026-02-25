from pickle import FALSE

from .bot import bot
from config import TELEGRAM_CHAT_ID
from utils.logger import logger
from telebot import types 

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
        text=f"`{author}`:\n```ini {text}\n```",parse_mode="Markdown"
    )

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def send_telegram_photo(author, photo):
    bot.send_photo(caption=author, photo=photo, chat_id=TELEGRAM_CHAT_ID, parse_mode=None) #софа извини, я не кричу, ты не глухая, ты софа, я ебу игоря

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

    msg = f"🔔 В Discord зашел `{username or id}`\n\nВы знаете этого человека?"
    bot.send_message(TELEGRAM_CHAT_ID, msg, reply_markup=markup, parse_mode="Markdown")