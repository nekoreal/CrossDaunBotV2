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
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
 
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

#1059959321 sunya
#874183602
MODER_ID=1059959321
 

@bot.message_handler(
    func=lambda message: (message.caption or message.text or "").startswith("/add") and ((message.reply_to_message or message).content_type or None)=='photo',
    content_types=["photo","text"],
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
    caption=message.caption or message.text or ""
    user_id=message.from_user.id
    chat_id=message.chat.id
    message_id=message.id

    if message.content_type=="text":
        message=message.reply_to_message or None
    
    if user_id != MODER_ID :
        if len(caption[5:])>5:  caption=caption[5:]
        else:                   caption=""
        send_react(chat_id, message_id, status="wait")
        send_to_moderate_photo(message, caption=caption)
        return
    category_name = None
    if len(caption[5:])>5:
        category_name = caption[5:]

    photo = message.photo[-1] 
    file_info = bot.get_file(photo.file_id) 
    file_bytes = bot.download_file(file_info.file_path) 
    buffer = io.BytesIO(file_bytes)

    add_photo(tg_id=user_id, file_bytes=file_bytes, category=category_name)

    send_react(chat_id=chat_id, message_id=message_id)

def send_to_moderate_photo(message:Message|None, caption:str=""):
    file_id = message.photo[-1].file_id
    if not file_id: return

    caption=f"Фото от {message.from_user.username}\n\nПодпись:{caption or ""}"

    reply_markup = InlineKeyboardMarkup() 
    btn_yes = InlineKeyboardButton("✅ Save", callback_data=f"moderate|save|{message.chat.id}|{message.id}|{message.from_user.username}|{message.from_user.id}")
    btn_no = InlineKeyboardButton("❌ Delete", callback_data=f"moderate|delete|{message.chat.id}|{message.id}|{message.from_user.username}")
    reply_markup.add(btn_yes, btn_no) 

    bot.send_photo(
        chat_id=MODER_ID,
        photo=file_id,
        caption=caption,
        reply_markup=reply_markup
    )


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
        from_user = bot.get_chat_member(chat_id=TELEGRAM_CHAT_ID, user_id=photo["tg_id"]).user.username or None
        bot.send_photo(
            chat_id=message.chat.id,
            photo=photo["file_bytes"],
            caption=f"Photo ID: {photo['id']}\nCategory: {photo['category']}\nFrom: @{from_user}"
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
    

    
 