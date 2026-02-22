from utils.mini_utils import run_in_thread
from config import TELEGRAM_CHAT_ID
from telegram_bot.bot import bot
from utils.logger import logger
from telebot.types import Message
from ..tg_utils.reaction import send_react  
from dataclasses import dataclass, field
from typing import Dict, Optional

 
@dataclass
class PollData:
    is_active: bool = False
    phase: Optional[str] = None 
    candidates: Dict[int, str] = field(default_factory=dict)
    extra_rounds: int = 0
    time_for_voting: int = 24   * 60  * 60     # в секундах
    time_for_collecting: int = 24   * 60 * 60  # в секундах

    def clear(self,):
        """Полный сброс данных до начального состояния"""
        self.is_active=False
        self.phase=None
        self.candidates.clear()
        self.extra_rounds=0
        self.time_for_voting=1            *60 #in seconds
        self.time_for_collecting=1        *60 #in seconds

    def add_or_update_candidate(self, user_id: int, file_id: str):
        """
        Добавляет фото по ID пользователя. 
        Если пользователь уже присылал фото — перезаписывает (обновляет).
        """
        self.candidates[user_id] = file_id

    def is_candidate(self, user_id: int) -> bool:
        """Проверка: участвует ли уже этот пользователь"""
        return user_id in self.candidates
    
    def start_collecting(self):
        """Начало сохранения фото"""
        self.phase="collecting"
    
    def start_voting(self):
        """Начало голосования"""
        self.phase="voting"


    def check_message_for_collecting(self, message:Message):
        """Проверка сообщения на подходящие условия"""
        return self.phase=='collecting' and (message.caption or "").lower()=="#на_аву"




poll_data:PollData=PollData()


@bot.message_handler(
    commands=['start_poll'],
    content_types=["text"]
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)   
def start_contest(message:Message|None):
    if (poll_data.phase!=None): 
        msg = bot.send_message(TELEGRAM_CHAT_ID, "Конкурс уже идет!")
        run_in_thread(bot.delete_messages, TELEGRAM_CHAT_ID, [msg.id, message.id] ,time_sleep=10)
        return 
    
    poll_data.clear()
    poll_data.start_collecting()
    
    bot.send_message(TELEGRAM_CHAT_ID, f"Этап ожидание: Сбор заявок ({poll_data.time_for_collecting//3600} часа)\n\nПрисылайте фото с хэштегом #на_аву. У каждого только 1 вариант")
     
    run_in_thread(start_voting, time_sleep=poll_data.time_for_collecting)

@bot.message_handler(
    content_types=['photo'],
    func=poll_data.check_message_for_collecting
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)  
def handle_photo(message:Message):
    try:
        poll_data.add_or_update_candidate(message.from_user.id, message.photo[-1].file_id)
    except:
        msg = bot.send_message(TELEGRAM_CHAT_ID, "`Ошибка регистраии, извинись`", parse_mode="Markdown")
        run_in_thread(bot.delete_message, TELEGRAM_CHAT_ID, msg.id)
        return
    send_react(TELEGRAM_CHAT_ID,message.id) 
    


@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)  
def start_voting():
    if not poll_data.candidates :
        bot.send_message(TELEGRAM_CHAT_ID, "Никто не прислал фото. В `жопу` вас.", parse_mode="Markdown")
        poll_data.clear()
        return
    if len(poll_data.candidates)==1:
        file_id = list(poll_data.candidates.values())[0]
        msg = bot.send_photo(TELEGRAM_CHAT_ID, file_id, caption="`Победитель` по умолчанию, так как конкуренция отсутствует.", parse_mode="Markdown")
        poll_data.clear()
        return 
    

    poll_data.phase = 'voting'
    bot.send_message(TELEGRAM_CHAT_ID, f"Этап {poll_data.extra_rounds+1} Голосование ({poll_data.time_for_voting//3600} часа)\n\nНиже представлены все варианты.", parse_mode="Markdown")
     
    options = list(poll_data.candidates.values())
     
    for idx, file_id in enumerate(options, 1):
        bot.send_photo(TELEGRAM_CHAT_ID, file_id, caption=f"Вариант `{idx}`", parse_mode="Markdown")

    poll = bot.send_poll(
        TELEGRAM_CHAT_ID, 
        "Выберите лучшую аватарку:", 
        options=[f"Вариант №{i+1}" for i in range(len(options))],
        is_anonymous=True,
        allows_multiple_answers=True
    )
     
    run_in_thread(finish_voting, poll.message_id, time_sleep=poll_data.time_for_voting)

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)  
def finish_voting( poll_message_id):
    poll = bot.stop_poll(TELEGRAM_CHAT_ID, poll_message_id)
    results = {idx: option.voter_count for idx, option in enumerate(poll.options)}
    max_votes = max(results.values())
    winners_idx = [idx for idx, count in results.items() if count == max_votes]

    if len(winners_idx) == 1 or poll_data.extra_rounds >= 2: 
        bot.send_message(TELEGRAM_CHAT_ID, "Голосование закончено!")
        for idx in winners_idx:
            file_id = list(poll_data.candidates.values())[idx]
            bot.send_photo(TELEGRAM_CHAT_ID, file_id, caption="Победитель!")
        poll_data.clear()
    else: 
        poll_data.extra_rounds += 1
        if poll_data.extra_rounds >1:
            poll_data.time_for_voting=int(poll_data.time_for_voting//2)
         
        poll_data.candidates = {idx: list(poll_data.candidates.values())[idx] for idx in winners_idx}
        
        run_in_thread(start_voting) 