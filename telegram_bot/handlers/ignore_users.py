from telebot.types import Message

from telegram_bot.bot import bot

IGNORE_USERS = [
    862249650,
]

def check_ignore_list(message:Message):
    msg = message.reply_to_message or message
    return msg.from_user.id in IGNORE_USERS

@bot.message_handler(
    func=lambda message: check_ignore_list(message)
)
def ignore_users(message:Message):
    pass