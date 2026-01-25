

from config import TELEGRAM_CHAT_ID

from telebot.types import Message,ChatMember

from telegram_bot.bot import bot
from telegram_bot.tg_utils.reaction import send_react

from telegram_bot.tg_db import session_scope
from telegram_bot.tg_db.models.tg_user import TelegramUser
from telegram_bot.tg_db.models.tg_teg import TelegramTag
from telegram_bot.tg_db.db_controllers import user_controller, at_user_tag_controller, tag_controller

from utils.logger import logger
from utils.mini_utils import run_in_thread, escape_markdown


@bot.message_handler(
    content_types=['text'],
    func=lambda message: message.text.startswith("#") and len(message.text) > 1
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def trigger_tag_handler(message:Message):
    run_in_thread(trigger_tags, message)
    send_react(message.chat.id, message.message_id)

@bot.message_handler(
    content_types=['text'],
    commands = ['all', 'все']
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def trigger_all_handler(message:Message):
    run_in_thread(trigger_all, message)
    send_react(message.chat.id, message.message_id)

@bot.message_handler(
    content_types = ['text'],
    commands = ['alltags', 'всетеги']
)
@logger(
    txtfile = "telegram_bot.txt",
    print_log = True,
    raise_exc = False,
    only_exc = True,
    time_log = True,
)
def all_tags_handler(message:Message):
    run_in_thread(all_tags, message)
    send_react(message.chat.id, message.message_id)

@bot.message_handler(
    content_types=['text'],
    commands=['taginfo', 'тегинфо']
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def taginfo_handler(message: Message):
    run_in_thread(taginfo, message)
    send_react(message.chat.id, message.message_id)

@bot.message_handler(
    content_types=['text'],
    commands=['tags', 'теги']
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def tags_handler(message: Message):
    run_in_thread(tags, message)
    send_react(message.chat.id, message.message_id)

@bot.message_handler(
    content_types=['text'],
    commands=['-tag', '-тег']
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def delete_tag_handler(message: Message):
    run_in_thread(delete_tag, message)
    send_react(message.chat.id, message.message_id)

@bot.message_handler(
    content_types=['text'],
    commands=['+tag', '+тег']
)
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def add_tag_handler(message: Message):
    run_in_thread(add_tag, message)
    send_react(message.chat.id, message.message_id)




















@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def trigger_tags(message: Message):
    try:
        msg_split = message.text.split(" ")
        tag_name = msg_split[0][1:]
        text = ' '.join(msg_split[1:])
    except:
        bot_msg = bot.reply_to(message, "Неправильный ввод. Пидорский пример // tag text")
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id]))
        return
    with session_scope() as session:
        tag = session.query(TelegramTag).filter_by(tag=tag_name).first()
        if tag is None:
            bot.reply_to(message, "Тег не найден, как и твой член")
            return
        usernames = [
            res.user.username
            for at in tag.at_user_tag
            if ((res:=get_or_delete_user(at.user,session)) and at.user.tg_id != message.from_user.id)
        ]
        mentions = "@" + " @".join(usernames) if usernames else ""

        res = (
            f"{escape_markdown(mentions)}"
            f"\n\n#{tag.tag}\n`{message.from_user.username}`:\n{escape_markdown(text)}"
        )
        bot.send_message(message.chat.id,
                         res
                         ,parse_mode="Markdown")
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id]))


@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def taginfo(message: Message):
    try:
        msg_split = message.text.split(" ")
        tag_name = ' '.join(msg_split[1:])
    except:
        bot_msg=bot.reply_to(message, "Неправильный ввод. Пидорский пример /tag tag_name")
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id]), time_sleep=5)
        return
    with session_scope() as session:
        tag = session.query(TelegramTag).filter_by(tag=tag_name).first()
        if tag is None:
            bot_msg=bot.reply_to(message, "Тег не найден, как и твой член")
            run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id]), time_sleep=5)
            return
        res = (
            f"Тег `{tag.tag}`\n"
            f"```ini\n{escape_markdown( "\n".join(list(res.user.username for at in tag.at_user_tag if (res:=get_or_delete_user(at.user,session)) )))}\n""```")
        bot_msg = bot.reply_to(message,
                         res
                         , parse_mode="Markdown")
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id,bot_msg.message_id]), time_sleep=15)

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def trigger_all(message: Message):
    try:
        msg_split = message.text.split(" ")
        text = ' '.join(msg_split[1:])
    except:
        bot.reply_to(message, "Неправильный ввод. Пидорский пример // tag text")
        return
    with session_scope() as session:
        users = session.query(TelegramUser).all()
        res=(f"{escape_markdown("@"+" @".join(list( res.user.username for user in users if (res:=get_or_delete_user(user,session)) )))}"
                         f"\n\n`{message.from_user.username}`:\n{escape_markdown(text)}" )
        bot.send_message(message.chat.id,
                         res
                         ,parse_mode="Markdown")
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id]))

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def tags(message: Message):
    user = user_controller.get_user(message.from_user.id)
    if message.reply_to_message:
        user = user_controller.get_user(message.reply_to_message.from_user.id)
    bot_msg = bot.reply_to(message,
                 f"`{bot.get_chat_member( TELEGRAM_CHAT_ID ,user_id=user["tg_id"]).user.username}` теги:\n"
                 f"```ini\n"
                 f"{escape_markdown('\n'.join(list( user_controller.get_user_tags_by_tg_id(user["tg_id"]) )))}\n"
                 f"\n```"
                 ,parse_mode="Markdown",
                 )
    run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                  , time_sleep=10)

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def delete_tag(message: Message):
    if message.reply_to_message:
        if str(message.from_user.id) == "874183602":
            user = user_controller.get_user(message.reply_to_message.from_user.id)
        else:
            bot_msg = bot.reply_to(message,"Кто такой, чтобы такое делать")
            run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                          , time_sleep=5)
            return
    else:
        user = user_controller.get_user(message.from_user.id)
    try:
        tag_name = message.text[6:]
        if len(tag_name) < 2:
            raise Exception("Короткий тэг")
    except Exception as e:
        bot_msg = bot.reply_to(
            message,
            "Неверная команда `пидор`",
            parse_mode="Markdown",
        )
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                      , time_sleep=5)
        return
    bot_msg = bot.reply_to(
        message,
        f"Для `{bot.get_chat_member( TELEGRAM_CHAT_ID ,user_id=user["tg_id"]).user.username}`"
        f"\n{at_user_tag_controller.delete_at_user_tag(user["id"], tag_name)}",
        parse_mode="Markdown",
                 )
    with session_scope() as session:
        tag_controller.delete_unused_tags(session)
    run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                  , time_sleep=5)

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def add_tag(message: Message):
    if message.reply_to_message:
        if str(message.from_user.id) == "874183602":
            user = user_controller.get_user(message.reply_to_message.from_user.id)
        else:
            bot_msg = bot.reply_to(message, "Кто такой, чтобы такое делать")
            run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                          , time_sleep=5)
            return
    else:
        user = user_controller.get_user(message.from_user.id)
    try:
        tag_name = message.text[6:]
        if len(tag_name)<2:
            raise Exception("Короткий тэг")
    except Exception as e:
        bot_msg = bot.reply_to(
            message,
            "Неверная команда `пидор`",
            parse_mode="Markdown",
        )
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                      , time_sleep=5)
        return
    bot_msg = bot.reply_to(
        message,
        f"Для `{bot.get_chat_member(TELEGRAM_CHAT_ID, user_id=user["tg_id"]).user.username}`"
        f"\n{escape_markdown(user_controller.add_tag_to_user(user_id=user["id"], tag_name=tag_name))}",
        parse_mode="Markdown",
    )
    run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                  ,time_sleep=5)


@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def all_tags(message: Message):
    try:
        with session_scope() as session:
            tags_counts = tag_controller.get_tags_with_user_counts(session)
            if not tags_counts:
                bot.reply_to(message, "Нет ни одного тега.")
                return
            text = "*Теги и количество пользователей:*\n"
            for tag, count in sorted(tags_counts, key=lambda x: x[1], reverse=True):
                text += f"`{count}` — {tag}\n"
            bot_msg = bot.reply_to(message, text, parse_mode="Markdown")
            run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                          , time_sleep=10)
    except:
        bot_msg = bot.reply_to(message, "Ошибка")
        run_in_thread(bot.delete_messages, message.chat.id, list([message.message_id, bot_msg.message_id])
                      , time_sleep=10)


def get_or_delete_user(
        user:TelegramUser,
        session
)->ChatMember|None:
    try:
        return bot.get_chat_member(TELEGRAM_CHAT_ID, user.tg_id)
    except:
        session.delete(user)
        return None