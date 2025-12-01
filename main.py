from discord_bot import run_discord_bot
from telegram_bot import run_telegram_bot
import threading
import asyncio
from utils.logger import logger


@logger(
    txtfile="main.txt",
    print_log=True,
    raise_exc=False,
    only_exc=False,
    time_log=True,
)
def main():
    telegram_thread = threading.Thread(target=run_telegram_bot)
    telegram_thread.start()
    asyncio.run(run_discord_bot())

if __name__ == "__main__":
    main()