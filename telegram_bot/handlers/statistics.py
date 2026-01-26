
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

STATS_MAP = {
        'text': TelegramUser.msg_count,
        'photo': TelegramUser.photo_count,
        'video': TelegramUser.video_count,
        'sticker': TelegramUser.sticker_count
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
def text_statistic(message:Message):
    if message.chat.id != TELEGRAM_CHAT_ID:
        return
    user = user_controller.get_user(message.from_user.id)

    target_column = STATS_MAP.get(message.content_type)
    if target_column:
        with session_scope() as session:
            session.query(TelegramUser). \
                filter(TelegramUser.tg_id == message.from_user.id). \
                update({target_column: target_column + 1})

    send_react_for_user(message.chat.id, message.message_id, message.from_user.id)