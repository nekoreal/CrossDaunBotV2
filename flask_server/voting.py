import hmac , hashlib
from flask import Blueprint,request,jsonify, send_file, abort, session, redirect, url_for , render_template
from sqlalchemy import text as sql_text#для сырых запросов текстом пример: result = db.session.execute(sql_text("update user set is_admin=True where username='admin';"))
from sqlalchemy.sql.functions import current_user
from io import BytesIO  
from config import TELEGRAM_BOT_USERNAME, TELEGRAM_TOKEN, MODER_ID
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

voting_bp=Blueprint('voting_bp', __name__)
 

@voting_bp.route("/vote/start")
def start_vote():  
    return "Ошибка авторизации: недействительная подпись или вы не член сообщества заводчан", 400


@voting_bp.route("/vote/connect")
def connect_to_voting():  
    return "Ошибка авторизации: недействительная подпись или вы не член сообщества заводчан", 400

 