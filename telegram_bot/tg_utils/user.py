from ..bot import bot
from config import TELEGRAM_CHAT_ID



def get_username_by_tgid(tg_id:int|str)->str|None:
    try:
        tg_id=int(tg_id)
    except:
        return None
    user=bot.get_chat_member(TELEGRAM_CHAT_ID, tg_id).user or None
    return user.username or f"id:{tg_id}"