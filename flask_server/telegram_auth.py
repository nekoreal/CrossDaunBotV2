import hmac , hashlib
from flask import Blueprint,request,jsonify, send_file, abort, session, redirect, url_for , render_template
from sqlalchemy import text as sql_text#для сырых запросов текстом пример: result = db.session.execute(sql_text("update user set is_admin=True where username='admin';"))
from sqlalchemy.sql.functions import current_user
from io import BytesIO  
from config import TELEGRAM_BOT_USERNAME, TELEGRAM_TOKEN, MODER_ID, ADMIN_ID
from flask_server.voting import is_started_poll
from telegram_bot.tg_db.db_controllers.user_controller import find_user_by_tg_id

def verify_telegram_data(data: dict, token: str) -> bool:
    check_hash = data.get("hash")
    if not check_hash:
        return False 
    data_check_list = [f"{k}={v}" for k, v in data.items() if k != "hash"]
    data_check_list.sort()
    data_check_string = "\n".join(data_check_list)

    secret_key = hashlib.sha256(token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(calculated_hash, check_hash)

entry_telegram_bp=Blueprint('entry_telegram_bp', __name__)


@entry_telegram_bp.route("/auth_telegram")
def auth_telegram(): 
    data = request.args.to_dict()
 
    if verify_telegram_data(data, TELEGRAM_TOKEN) and find_user_by_tg_id(int(data.get("id"))): 
        session["user"] = {
            "id": data.get("id"),
            "username": data.get("username", ""),
            "photo_url": data.get("photo_url", ""),
            "is_moder": int(data.get("id")) in [MODER_ID, ADMIN_ID] 
        } 
        return redirect(url_for("entry_telegram_bp.home"))
    
    return "Ошибка авторизации: недействительная подпись или вы не член сообщества заводчан", 400

@entry_telegram_bp.route("/home")
def home():
    user = session.get("user")
    return render_template("home.html", user=user, bot_username=TELEGRAM_BOT_USERNAME, is_started=is_started_poll())

@entry_telegram_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("entry_telegram_bp.home"))

 