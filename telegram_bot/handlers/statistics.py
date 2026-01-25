
from config import TELEGRAM_CHAT_ID

from telebot.types import Message,ChatMember

from telegram_bot.bot import bot
from telegram_bot.tg_utils.reaction import send_react_for_user

from telegram_bot.tg_db import session_scope
from telegram_bot.tg_db.models.tg_user import TelegramUser
from telegram_bot.tg_db.models.tg_teg import TelegramTag
from telegram_bot.tg_db.db_controllers import user_controller, at_user_tag_controller, tag_controller

from utils.logger import logger
from utils.mini_utils import run_in_thread, escape_markdown

@bot.message_handler(
    content_types=['text']
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def text_statistic(message:Message):


    send_react_for_user(message.chat.id, message.message_id, message.from_user.id)