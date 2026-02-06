
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


DAY_COUNT_MSG=0

def get_day_msg_count():
    global DAY_COUNT_MSG
    return DAY_COUNT_MSG

STATS_MAP = {
        'text': TelegramUser.msg_count,
        'photo': TelegramUser.photo_count,
        'video': TelegramUser.video_count,
        'sticker': TelegramUser.sticker_count,
        'nya': TelegramUser.nya_count,
    }

STATS_MAP_MONTH = {
        'text': TelegramUser.msg_count_month,
        'photo': TelegramUser.photo_count_month,
        'video': TelegramUser.video_count_month,
        'sticker': TelegramUser.sticker_count_month,
        'nya': TelegramUser.nya_count_month,
    }

@bot.message_handler(
    content_types=['text','photo','video','sticker'],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def msg_statistic(message:Message):
    if message.chat.id != TELEGRAM_CHAT_ID:
        return
    user = user_controller.get_user(message.from_user.id)
    global DAY_COUNT_MSG 
    DAY_COUNT_MSG+=1
    text = message.text or "" 
    target_column = STATS_MAP.get('nya') if text.startswith("/nya") else STATS_MAP.get(message.content_type) 
    target_column_month = STATS_MAP_MONTH.get('nya') if text.startswith("/nya") else STATS_MAP_MONTH.get(message.content_type) 

    if target_column:
        with session_scope() as session:
            session.query(TelegramUser). \
                filter(TelegramUser.tg_id == message.from_user.id). \
                update({target_column: target_column + 1})
            session.query(TelegramUser). \
                filter(TelegramUser.tg_id == message.from_user.id). \
                update({target_column_month: target_column_month + 1})

    send_react_for_user(message.chat.id, message.message_id, message.from_user.id)