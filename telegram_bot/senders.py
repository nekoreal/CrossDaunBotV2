from pickle import FALSE

from .bot import bot
from config import TELEGRAM_CHAT_ID
from utils.logger import logger

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
        text=f"`{author}`: {text}",parse_mode="Markdown"
    )

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def send_telegram_photo(author, photo):
    bot.send_photo(caption=author, photo=photo, chat_id=TELEGRAM_CHAT_ID) #софа извини, я не кричу, ты не глухая, ты софа, я ебу игоря