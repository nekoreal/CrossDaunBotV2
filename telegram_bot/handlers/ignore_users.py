from telebot.types import Message

from telegram_bot.bot import bot

IGNORE_USERS = [
    862249650, 
]

def check_ignore_list(message:Message): 
    if message.reply_to_message:
        return message.reply_to_message.from_user.id in IGNORE_USERS or message.from_user.id in IGNORE_USERS
    return message.from_user.id in IGNORE_USERS

@bot.message_handler(
    func=lambda message: check_ignore_list(message),
    content_types=['text','photo','video','sticker','document','audio','voice','video_note','location','contact', 'animation', "poll"],
)
def ignore_users(message:Message):  
    pass