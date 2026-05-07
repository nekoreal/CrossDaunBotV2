from telebot.types import Message

from config import TELEGRAM_CHAT_ID
from telegram_bot.bot import bot

@bot.message_handler(
    func=lambda message: message.chat.id!=TELEGRAM_CHAT_ID,
    content_types=['text','photo','video','sticker','document','audio','voice','video_note','location','contact', 'animation', "poll"],
)
def only_from_group(message:Message):
    pass
