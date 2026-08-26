from telegram_markdown_converter import convert_markdown
from utils.mini_utils import run_in_thread
from config import TELEGRAM_CHAT_ID
from telegram_bot.bot import bot
from utils.logger import logger
from telebot.types import Message
from ..tg_utils.reaction import send_react  
from dataclasses import dataclass, field
from typing import Dict, Optional  
import io
from ..tg_db.db_controllers.photo_controller import add_photo, get_random_photo_url, get_random_photo , move_photo_to_category, delete_photo
 
"""@dataclass
class PollData:
    is_active: bool = False
    phase: Optional[str] = None 
    candidates: Dict[int, str] = field(default_factory=dict)
    extra_rounds: int = 0
    time_for_voting: int = 24 * 60 * 60     # в секундах
    time_for_collecting: int = 24 * 60 * 60    # в секундах
   
poll_data:PollData=PollData()
"""
 

@bot.message_handler(
    func=lambda message: (message.caption or "").startswith("/add "),
    content_types=["photo"],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)   
def add_photo_from_tg(message:Message|None): 
    run_in_thread(add_photo_from_tg_thread, message)

def add_photo_from_tg_thread(message:Message|None):
    if message.from_user.id != 874183602:
        bot.reply_to(message, "Зашита от ЦП.")
        return
    category_name = None
    if len(message.caption or "")>5:
        category_name = message.caption[5:]

    photo = message.photo[-1] 
    file_info = bot.get_file(photo.file_id) 
    file_bytes = bot.download_file(file_info.file_path) 
    buffer = io.BytesIO(file_bytes)

    add_photo(tg_id=message.from_user.id, file_bytes=file_bytes, category=category_name)

    send_react(chat_id=message.chat.id, message_id=message.message_id)


@bot.message_handler(
    func=lambda message: (message.text or "") == "/photo", 
    content_types=["text"],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)   
def get_photo(message:Message|None):  
    run_in_thread(get_photo_thread, message)

def get_photo_thread(message:Message|None):
    send_react(chat_id=message.chat.id, message_id=message.message_id) 
    photo = get_random_photo() 

    if photo:
        bot.send_photo(
            chat_id=message.chat.id,
            photo=photo["file_bytes"],
            caption=f"Photo ID: {photo['id']}\nCategory: {photo['category']}"
        ) 
    else: 
        bot.reply_to(message, "No photo found.")    


 
@bot.message_handler(
    func=lambda message: (message.text or "") == "/url_photo", 
    content_types=["text"],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)   
def get_url_photo(message:Message|None):  
    run_in_thread(get_url_photo_thread, message)

def get_url_photo_thread(message:Message|None):
    send_react(chat_id=message.chat.id, message_id=message.message_id) 
    url_photo = get_random_photo_url(with_category=False) 
    if url_photo:
        bot.reply_to(message, url_photo) 
    else: 
        bot.reply_to(message, "No photo  found.")
    

    
 