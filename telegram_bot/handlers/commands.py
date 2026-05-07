
from config import TELEGRAM_CHAT_ID

from telebot.types import Message ,ChatMember

from telegram_bot.bot import bot
from telegram_bot.tg_db.db_controllers.user_controller import set_follow_status
from telegram_bot.tg_utils.reaction import send_react

from telegram_bot.tg_db import session_scope
from telegram_bot.tg_db.models.tg_user import TelegramUser
from telegram_bot.tg_db.models.tg_teg import TelegramTag
from telegram_bot.tg_db.db_controllers import user_controller, at_user_tag_controller, tag_controller
from telegram_markdown_converter  import convert_markdown
from utils.logger import logger
from utils.mini_utils import run_in_thread, escape_markdown


@bot.message_handler(
    content_types=['text'],
    commands=['follow', 'подписаться'],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def follow_ds_info (message :Message):
    if set_follow_status(message.from_user.id, True):
        botmsg = bot.reply_to(message, "Ты подписался на Sweety Fox")
        send_react(TELEGRAM_CHAT_ID, message.id)
        run_in_thread(bot.delete_messages, TELEGRAM_CHAT_ID, [botmsg.id, message.id], time_sleep=5)
        return
    botmsg = bot.reply_to(message, "Не получилось подписаться на Sweety Fox")
    run_in_thread(bot.delete_messages, TELEGRAM_CHAT_ID, [botmsg.id, message.id], time_sleep=5)

@bot.message_handler(
    content_types=['text'],
    commands=['unfollow', 'отподписаться'],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def unfollow_ds_info (message :Message):
    if set_follow_status(message.from_user.id, False):
        botmsg = bot.reply_to(message, "Ты отписался на Sweety Fox")
        send_react(TELEGRAM_CHAT_ID, message.id)
        run_in_thread(bot.delete_messages, TELEGRAM_CHAT_ID, [botmsg.id, message.id], time_sleep=5)
        return
    botmsg = bot.reply_to(message, "Не получилось отписаться на Sweety Fox")
    run_in_thread(bot.delete_messages, TELEGRAM_CHAT_ID, [botmsg.id, message.id], time_sleep=5)

