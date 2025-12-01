
from .bot import bot


@bot.message_handler(commands=['ds'])
def handle_ds(message):
    if message.from_user.id == bot.user.id:
        return
    print(message.from_user.username, message.text)