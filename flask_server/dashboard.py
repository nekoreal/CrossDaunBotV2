from flask import Flask, render_template
from telegram_bot.tg_db import session_scope
from telegram_bot.tg_db.models.tg_user import TelegramUser
from telegram_bot.tg_db.models.tg_teg import TelegramTag
from telegram_bot.tg_db.models.tg_at_user_tag import UserTagAssociation
from telegram_bot.bot import bot
from config import TELEGRAM_CHAT_ID
from telegram_bot.tg_utils.avatar import get_and_resize_chat_photo
from telegram_bot.handlers.statistics import get_day_msg_count
app = Flask(__name__)


@app.route('/')
def index():
    with session_scope() as session:
        users = session.query(TelegramUser).all()
        users_data = []

        for user in users: 
            d = user.to_dict()
 
            try:
                member = bot.get_chat_member(TELEGRAM_CHAT_ID, user.tg_id)
                u = member.user
                d["username_plain"] = u.username or u.first_name or "User"
                d["profile_url"] = f"https://t.me/{u.username}" if u.username else f"tg://user?id={user.tg_id}"
                # Ссылка на аватарку (через публичный редирект телеги)
                d[
                    "avatar"] = f"https://t.me/i/userpic/320/{u.username}.jpg" if u.username else "https://ui-avatars.com/api/?name=?"
            except Exception as e:
                d["username_plain"] = f"ID: {user.tg_id}"
                d["profile_url"] = "#"
                d["avatar"] = "https://ui-avatars.com/api/?name=?"

            users_data.append(d)   
    users_data = sorted(users_data, key=lambda x: x["msg_count"], reverse=True)
    data={
        "users": users_data,
        "day_msg_count": get_day_msg_count(), 
        "total_msg_count": sum(user["msg_count"] for user in users_data),
        "month_user": users_data[0] if users_data else None,
    }  
    return render_template('index.html', data=data, reverse=True)

def run_flask():
    app.run(debug=False, host='0.0.0.0', port=5002)