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
from ..tg_db.db_controllers.photo_controller import get_all_categories,get_photo_by_id,add_or_find_category , add_photo, get_random_photo_url, get_random_photo , move_photo_to_category, delete_photo
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import MODER_ID
 
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

in_adding={}

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)   
def delete_from_adding(tg_id:int):
    try:
        in_adding.pop(tg_id)
    except:
        pass

@bot.message_handler(
    func=lambda message: ( message.text or "").startswith("/start_add") ,
    content_types=["text"],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)   
def start_adding_photo_from_tg(message:Message|None): 
    if message.from_user.id != MODER_ID:
        bot.reply_to(message=message, text=f"Функция только для модераторов")
        return
    if message.from_user.id in in_adding.keys():
        bot.reply_to(message=message, text=f"Ты уже начал эту функцию, советую остановить и запустить заного. /stop_add /start_add")
        return
    category=message.text[11:] or None
    in_adding[message.from_user.id]=category
    if category: add_or_find_category(category)
    bot.reply_to(message=message, text=f"В течении 30 минут все присланные фото идут, чтобы остановить самому /stop_add ")
    run_in_thread(delete_from_adding, message.from_user.id, time_sleep=1800)

@bot.message_handler(
    func=lambda message: ( message.text or "").startswith("/stop_add") ,
    content_types=["text"],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)   
def stop_adding_photo_from_tg(message:Message|None): 
    if not (message.from_user.id in in_adding.keys()):
        bot.reply_to(message=message, text=f"Ты и не начинал")
        return 
    delete_from_adding(message.from_user.id)
    bot.reply_to(message=message, text=f"Остановлено")

@bot.message_handler(
    func=lambda message: message.from_user.id == MODER_ID and message.from_user.id in in_adding.keys() ,
    content_types=["photo"],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)   
def in_adding_photo(message:Message|None): 
    if message.from_user.id != MODER_ID:
        bot.reply_to(message=message, text=f"Функция только для модераторов")
        return
    category_name=in_adding[message.from_user.id] 
    photo = message.photo[-1] 
    file_info = bot.get_file(photo.file_id) 
    file_bytes = bot.download_file(file_info.file_path) 
    buffer = io.BytesIO(file_bytes)
    if not add_photo(tg_id=message.from_user.id, file_bytes=file_bytes, category_name=category_name):
        bot.reply_to(message=message, text=f"Ошибка, попробуйте заного чуть позже")




@bot.message_handler(
    func=lambda message: (message.text or "").startswith("/themes"), 
    content_types=["text"],
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)   
def get_themes(message:Message|None):  
    run_in_thread(get_themes_thread, message)

def get_themes_thread(message: Message | None): 
    categories = get_all_categories()

    lines = ["📊  Статистика по категориям: \n"]
    total_photos = sum(count for _, count in categories)

    for cat_title, cat_count in categories:
        lines.append(f"▫️ {cat_title}: {cat_count} шт.")

    lines.append(f"\n📈 Всего фотографий: {total_photos}")

    if message:
        bot.reply_to(message, text="\n".join(lines), parse_mode="Markdown")


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
        send_to_moderate_photo(message, caption=caption, chat_id_for_callback=chat_id, messge_id_for_callback=message_id)
        return  
    category_name = caption[5:] or None

    photo = message.photo[-1] 
    file_info = bot.get_file(photo.file_id) 
    file_bytes = bot.download_file(file_info.file_path) 
    buffer = io.BytesIO(file_bytes)

    status="yes"
    if not add_photo(tg_id=user_id, file_bytes=file_bytes, category_name=category_name):
        status="no"
    send_react(chat_id=chat_id, message_id=message_id, status=status)
        


def send_to_moderate_photo(
        message:Message|None,
        messge_id_for_callback,
        chat_id_for_callback,
        caption:str=""
        ):
    file_id = message.photo[-1].file_id
    if not file_id: return

    caption=f"Фото от {message.from_user.username}\n\nПодпись:{caption or ""}"

    reply_markup = InlineKeyboardMarkup() 
    btn_yes = InlineKeyboardButton("✅ Save", callback_data=f"moderate|save|{chat_id_for_callback}|{messge_id_for_callback}|{message.from_user.username}|{message.from_user.id}")
    btn_no = InlineKeyboardButton("❌ Delete", callback_data=f"moderate|delete|{chat_id_for_callback}|{messge_id_for_callback}|{message.from_user.username}")
    reply_markup.add(btn_yes, btn_no) 

    bot.send_photo(
        chat_id=MODER_ID,
        photo=file_id,
        caption=caption,
        reply_markup=reply_markup
    )


@bot.message_handler(
    func=lambda message: (message.text or "").startswith("/photo"), 
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
    id_or_name = (message.text[7:] or None)
    category_name,id=None, None
    try:
        id = int(id_or_name)
    except:
        category_name=id_or_name or None
    if id: 
        photo = get_photo_by_id(id)  
    else:
        photo = get_random_photo(category=category_name) 

    if photo:
        from_user = bot.get_chat_member(chat_id=TELEGRAM_CHAT_ID, user_id=photo["tg_id"]).user.username or None
        bot.send_photo(
            chat_id=message.chat.id,
            photo=photo["file_bytes"],
            caption=f"Photo ID: {photo['id']}\nCategory: {photo['category']}\nFrom: @{from_user}"
        ) 
    else: 
        bot.reply_to(message, "No photo found.плаки плаки")    


 
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
    

    
 