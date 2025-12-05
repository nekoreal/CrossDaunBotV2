from discord_bot import run_discord_bot
from telegram_bot import run_telegram_bot
import threading
import asyncio
from utils.logger import logger
from telegram_bot.tg_db import engine, Base
from telegram_bot.tg_db.models.tg_user import TelegramUser
from telegram_bot.tg_db.models.tg_teg import TelegramTag
from telegram_bot.tg_db.models.tg_at_user_tag import UserTagAssociation
import logging






@logger(
    txtfile="main.txt",
    print_log=True,
    raise_exc=False,
    only_exc=False,
    time_log=True,
)
def main():
    Base.metadata.create_all(bind=engine)
    telegram_thread = threading.Thread(target=run_telegram_bot)
    telegram_thread.start()
    asyncio.run(run_discord_bot())

if __name__ == "__main__":
    main()