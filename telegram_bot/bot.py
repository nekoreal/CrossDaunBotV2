import telebot
from config import TELEGRAM_TOKEN
from utils.logger import logger, make_log


bot = telebot.TeleBot(TELEGRAM_TOKEN)

@logger(
    txtfile="telegram_bot.log",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def run_telegram_bot():
    import telegram_bot.handlers
    while True:
        try:
            print("Telegram Bot Starting")
            bot.polling(none_stop=True)
        except Exception as e:
            print(e)
            make_log(
                txtfile="telegram_bot.log",
                text=f"Telegram bot error: {e}",
                print_log=True,
                time_log=True
            )