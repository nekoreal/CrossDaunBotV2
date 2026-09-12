import time
from dataclasses import dataclass
from threading import Lock
from flask import Blueprint, request, session, redirect, url_for, render_template
from flask_socketio import emit, disconnect

from telegram_bot.tg_db.db_controllers.photo_controller import (
    photo_urls_paginate,
    get_all_categories_dict
) 
 
gallery_bp = Blueprint('gallery_bp', __name__)
  

@gallery_bp.route("/gallery/get_categories")
def get_categories():
    user = session.get("user")
    if not user:
        return "Ошибка авторизации", 400

    return get_all_categories_dict(), 200



@gallery_bp.route("/gallery/paginate_photos")
def paginate_photos():
    user = session.get("user")
    if not user:
        return "Ошибка авторизации", 400

    category_id = request.args.get('category', type=str)
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=32, type=int)
    

    return photo_urls_paginate(category_id=category_id, page=page, limit=limit), 200

@gallery_bp.route("/gallery")
def gallery_page():
    user = session.get("user")
    if not user:
        return redirect(url_for("entry_telegram_bp.home")) 
    return render_template("gallery.html")




 