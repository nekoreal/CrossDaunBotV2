import asyncio

from telegram_markdown_converter import convert_markdown

from utils.logger import logger
from discord_bot.senders import send_tts
from telegram_bot.bot import bot 
from discord_bot.bot import get_discord_loop 
from .discord_commands import get_pending_requests 
from telebot.types import CallbackQuery
from config import TELEGRAM_CHAT_ID 
from utils.mini_utils import run_in_thread 
from discord_bot.ds_utils.invite_with_role import verify_role
from ..tg_utils.reaction import send_react
import io
from ..tg_db.db_controllers.photo_controller import add_photo
from .photo_sorting import MODER_ID

@bot.callback_query_handler(
        func=lambda call: call.data.startswith('verify|')
        )
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def handle_verify_ds(call:CallbackQuery): 
    split=call.data.split('|')
    ans = split[1]
    username = split[3]
    if ans=='yes': 
        id = split[2]
        bot.edit_message_text( convert_markdown(f"Новый пользователь `{username}` получил роль\n\nБлагодаря `{call.from_user.username}` ") ,TELEGRAM_CHAT_ID,call.message.id, parse_mode="Markdown")
        asyncio.run_coroutine_threadsafe(verify_role(id), get_discord_loop())
        return
    bot.edit_message_text( f"`{username}` не получит мороженку\n\nБлагодаря `{call.from_user.username}` " ,TELEGRAM_CHAT_ID,call.message.id, parse_mode="Markdown") 
    run_in_thread(bot.delete_message,TELEGRAM_CHAT_ID,call.message.id, time_sleep=30)
    

@bot.callback_query_handler(
        func=lambda call: call.data.startswith('tts|')
        )
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def handle_tts_selection(call:CallbackQuery): 
    req_data = get_pending_requests().get(call.message.message_id) 
    if not req_data:
            bot.answer_callback_query(call.id, "Запрос устарел. Извинись")
            return
    
    if call.from_user.id != req_data['user_id']:
        bot.answer_callback_query(call.id, "Это не ваша команда! Извинись 😡", show_alert=True)
        return 
    
    bot.delete_message(call.message.chat.id, call.message.message_id)

    channel_id = int(call.data.split('|')[1])
    text = req_data['text']
 
    
    
    future = asyncio.run_coroutine_threadsafe(send_tts(channel_id, text), get_discord_loop())
    
    if future.result(): 
        bot.answer_callback_query(call.id, f"✅ Озвучено в Discord: {text}")
    else:
        bot.answer_callback_query(call.id, "Ошибка: Канал не найден")


@bot.callback_query_handler(
        func=lambda call: call.data.startswith('moderate|')
        )
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def handle_moderate(call:CallbackQuery):
    if call.from_user.id != MODER_ID:
        bot.answer_callback_query(call.id, f"❌ Отказано в доступе ❌")
        return
    call_msg = call.message.message_id
    call_split = call.data.split("|")
    print(call_split)
    chat_id=int(call_split[2])
    message_id=int(call_split[3])
    decision="Принято"
    message=call.message
    if call_split[1]=="delete":
        bot.answer_callback_query(call.id, f"❌ Вы отклонили ❌")
        decision="Отклонено"
        send_react(chat_id=chat_id, message_id=message_id ,status="no")
    else:
        photo = message.photo[-1] 
        file_info = bot.get_file(photo.file_id) 
        file_bytes = bot.download_file(file_info.file_path) 
        buffer = io.BytesIO(file_bytes)
        user_id=int(call_split[5])
        add_photo(tg_id=user_id, file_bytes=file_bytes)

        bot.answer_callback_query(call.id, f"✅ Вы приняли ✅")
        decision="Сохранено"
        send_react(chat_id=chat_id, message_id=message_id )
         
    bot.edit_message_caption(chat_id=message.chat.id, message_id=message.id, caption= f"От: @{call_split[4]}\n\nИтог:{decision}" ,reply_markup=None)

