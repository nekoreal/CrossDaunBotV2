import asyncio

from utils.logger import logger
from discord_bot.senders import send_tts
from telegram_bot.bot import bot 
from discord_bot.bot import get_discord_loop 
from .discord_commands import get_pending_requests 



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
def handle_tts_selection(call): 
    req_data = get_pending_requests().get(call.message.message_id)

    if not req_data:
            bot.answer_callback_query(call.id, "Запрос устарел. Извинись")
            return
    
    if call.from_user.id != req_data['user_id']:
        bot.answer_callback_query(call.id, "Это не ваша команда! Извинись 😡", show_alert=True)
        return 
    
    channel_id = int(call.data.split('|')[1])
    text = req_data['text']
 
    

    future = asyncio.run_coroutine_threadsafe(send_tts(channel_id, text), get_discord_loop())
    
    if future.result(): 
        bot.answer_callback_query(call.id, f"✅ Озвучено в Discord: {text}")
    else:
        bot.answer_callback_query(call.id, "Ошибка: Канал не найден")
