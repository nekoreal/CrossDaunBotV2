import telebot
from config import TELEGRAM_TOKEN
from utils.logger import logger, make_log

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def run_telegram_bot():
    while True:
        try:
            print('polling')
            bot.polling(none_stop=True)
        except Exception as e:
            print(e)
            make_log(
                txtfile="telegram_bot.log",
                text=f"Telegram bot error: {e}",
                print_log=True,
                time_log=True
            )