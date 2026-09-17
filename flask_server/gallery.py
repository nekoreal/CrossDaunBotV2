import time
from dataclasses import dataclass
from threading import Lock
from flask import Blueprint, jsonify, request, session, redirect, url_for, render_template
from flask_socketio import emit, disconnect
from flask_pydantic import validate
from validator.gallery_validator import GalleryPaginateParams

from telegram_bot.tg_db.db_controllers.photo_controller import (
    photo_urls_paginate,
    get_all_categories_dict,
    move_photo_to_category
) 
 
gallery_bp = Blueprint('gallery_bp', __name__)
  

@gallery_bp.route("/gallery/get_categories")
def get_categories():  
    return get_all_categories_dict(), 200 

@gallery_bp.route("/gallery/paginate_photos")
@validate(
     query=GalleryPaginateParams
)
@gallery_bp.route("/gallery/paginate_photos", methods=["GET"])
@validate(query=GalleryPaginateParams)
def paginate_photos(query: GalleryPaginateParams): 

    result = photo_urls_paginate(
        categories=query.categories,
        page=query.page,
        limit=query.limit,
        sort_by=query.sort_by,
        sort_order=query.sort_order,
    )

    return jsonify(result), 200

@gallery_bp.route("/gallery")
def gallery_page(): 
    user = session.get("user") or None
    return render_template("gallery.html", user=user)


@gallery_bp.route("/gallery/resort")
def resort_photo():
    user = session.get("user")
    if not user or not user.get("is_moder"): 
            return {"message": "Недостаточно прав"}, 400

    photo_id = request.args.get('photo_id', type=str) 
    if move_photo_to_category(photo_id=photo_id, category_name=None):
        return {"message": "Отправлено на пересортировку"}, 200
    return {"message": "Ошибка"}, 400



 