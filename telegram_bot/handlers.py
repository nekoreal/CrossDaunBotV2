import asyncio

from pydantic import Tag

from config import TELEGRAM_CHAT_ID
from utils.logger import logger
from discord_bot.senders import send_embed_to_discord, send_reply_embed_to_discord
from .bot import bot
from .tg_utils.avatar import get_user_avatar
from telebot.types import Message, ChatMember
from discord_bot.bot import get_discord_loop
from io import BytesIO
from discord_bot.ds_utils.ds_online_info import get_online_info
from random import randint
from .tg_utils.reaction import send_react,send_react_for_user
import threading
from utils.model_gpt import dialoggpt, askgpt
from discord_bot.ds_utils.invite_with_role import get_invite_link
from .tg_db.db_controllers import user_controller, at_user_tag_controller, tag_controller
from .tg_utils.mini_utils import escape_markdown, run_in_thread
from .tg_db import session_scope
from .tg_db.models.tg_teg import TelegramTag
from .tg_db.models.tg_user import TelegramUser
from .tg_db.db_controllers.tag_controller import get_tags_with_user_counts, delete_unused_tags



@bot.message_handler(content_types=['photo','text'])
@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=True,
    only_exc=True,
    time_log=True,
)
def message_handler(message:Message):
    print(message.from_user.id)
    if str(message.from_user.id) == "862249650":
        return
    user=user_controller.get_user(message.from_user.id)
    text = message.text if message.content_type == 'text' else (message.caption if message.caption else "")
    if message.from_user.id == bot.user.id:
        return
    if text.startswith("/ds ") or text.startswith("/дс ") or text in ["/ds", "/дс"]:
        ds(message)
        return
    elif text.startswith("/2ds") or text.startswith("/2дс"):
        to_ds(message)
        return
    elif text.startswith("/dsinfo") or text.startswith("/дсинфо"):
        dsinfo(message)
        return
    elif text.startswith("/invite") or text.startswith("/приглашение"):
        invite(message)
        return
    elif text.startswith("/n ") or text.startswith("/н "):
        bot.reply_to(message, askgpt(message.text[2:]))
        send_react(message.chat.id, message.message_id)
        return
    elif str(message.reply_to_message.from_user.id) != "862249650" if message.reply_to_message else True:
        if text.startswith("/+tag ") or text.startswith("/+тег "):
            run_in_thread(add_tag,message)
            send_react(message.chat.id, message.message_id)
            return
        elif text.startswith("/-tag ") or text.startswith("/-тег "):
            run_in_thread(delete_tag, message)
            send_react(message.chat.id, message.message_id)
            return
        elif text.startswith("/tags") or text.startswith("/теги"):
            run_in_thread(tags, message)
            send_react(message.chat.id, message.message_id)
            return
        elif text.startswith("/alltags") or text.startswith("/всетеги"):
            run_in_thread(alltags, message)
            send_react(message.chat.id, message.message_id)
            return
        elif text.startswith("/taginfo ") or text.startswith("/тегинфо "):
            run_in_thread(taginfo,message)
            send_react(message.chat.id, message.message_id)
            return
        elif text.startswith("/all ") or text.startswith("/все "):
            run_in_thread(trigger_all, message)
            send_react(message.chat.id, message.message_id)
            return
        elif text.startswith("#") and len(text)>1 and message.content_type=="text":
            run_in_thread(trigger_tags, message)
            send_react(message.chat.id, message.message_id)
            return


    send_react_for_user(message.chat.id, message.message_id, message.from_user.id)
    if len(text)>25:
        if randint(0,17)==7:
            try:
                threading.Thread(target=bot.reply_to, args=(message,dialoggpt(text, message.from_user.username),)).start()
                return
            except:
                pass

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
        print('fffff'+res.user.username for user in users if (res:=get_or_delete_user(user,session)))
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
            if (res:=get_or_delete_user(at.user,session) and at.user.tg_id != message.from_user.id)
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
def alltags(message: Message):
    try:
        with session_scope() as session:
            tags_counts = get_tags_with_user_counts(session)
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
        delete_unused_tags(session)
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
def invite(message: Message):
    res = asyncio.run_coroutine_threadsafe(
        get_invite_link()
        , get_discord_loop()
    ).result()
    bot.reply_to(message, res, parse_mode="Markdown")
    send_react(message.chat.id, message.message_id)


@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def dsinfo(message:Message):
    res = asyncio.run_coroutine_threadsafe(
        get_online_info()
        ,get_discord_loop()
    ).result()
    bot.reply_to(message,res, parse_mode="Markdown")
    send_react(message.chat.id, message.message_id)

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def ds(message:Message):
    kwargs = {
        "sender" : message.from_user.username,
        "senderlink" : f"https://t.me/{message.from_user.username}" if message.from_user.username else message.from_user.id,
        "text" : message.text[3:] if message.content_type=='text' else message.caption[3:],
        "senderavatar" : get_user_avatar(bot, message.from_user.id)
    }
    if message.content_type=='photo' :
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        photo_bytes = BytesIO(bot.download_file(file_info.file_path))
        kwargs.update({"photo":photo_bytes})
    asyncio.run_coroutine_threadsafe(
        send_embed_to_discord(  **kwargs  ),
        get_discord_loop()
    )
    send_react(message.chat.id, message.message_id)

@logger(
    txtfile="telegram_bot.txt",
    print_log=True,
    raise_exc=False,
    only_exc=True,
    time_log=True,
)
def to_ds(message:Message):
    if not message.reply_to_message:
        bot.reply_to(message, "Еблан, ты хоть выдели, что пересылаешь")
        return
    kwargs = {
        "sender" : message.from_user.username,
        "senderlink" : f"https://t.me/{message.from_user.username}" if message.from_user.username else message.from_user.id,
        "text" : message.reply_to_message.text if message.reply_to_message.content_type=='text' else (message.reply_to_message.caption or " "),
        "senderavatar" : get_user_avatar(bot, message.from_user.id),
        "rsender": message.reply_to_message.from_user.username,
        "rsenderavatar": get_user_avatar(bot, message.reply_to_message.from_user.id),
    }
    if message.reply_to_message.content_type=='photo' :
        file_id = message.reply_to_message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        photo_bytes = BytesIO(bot.download_file(file_info.file_path))
        kwargs.update({"photo":photo_bytes})
    asyncio.run_coroutine_threadsafe(
        send_reply_embed_to_discord(  **kwargs  ),
        get_discord_loop()
    )
    send_react(message.chat.id, message.message_id)

def get_or_delete_user(user:TelegramUser,session)->ChatMember|None:
    try:
        return bot.get_chat_member(TELEGRAM_CHAT_ID, user.tg_id)
    except:
        session.delete(user)
        return None
