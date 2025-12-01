from .bot import bot

def send_telegram_message(author, text):
    print(text)
    bot.send_message(f"`{author}`: {text}",parse_mode="Markdown")
    print("finished")