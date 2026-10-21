"""HTTP API скинов карт и админ-панели покера. Картинки скинов лежат в отдельном S3-бакете."""
import io
import re
import time
import uuid
from collections import OrderedDict
from threading import Lock
from flask import request, session, jsonify, Response, abort
from PIL import Image, ImageOps

from config import TELEGRAM_CHAT_ID
from s3 import skins_s3_client
from telegram_bot.bot import bot
from telegram_bot.tg_db.db_controllers.poker_controller import (
    create_skin, update_skin, delete_skin, get_owned_skin_ids, list_users_chips,
)
from flask_server.dashboard import socketio
from flask_server.poker import poker_bp, table, is_admin, STD_SKINS, SETTINGS_SPEC

RANKS = "AKQJT98765432"
SUITS = "shdc"
CARD_SIZE = (360, 504)            # 5:7, как у карт на столе
MAX_FILE_BYTES = 6 * 1024 * 1024
MAX_REQUEST_BYTES = 60 * 1024 * 1024
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
Image.MAX_IMAGE_PIXELS = 40_000_000

_img_cache: "OrderedDict[str, bytes]" = OrderedDict()
_img_cache_lock = Lock()
_bucket_ready = False


def _tg_id():
    user = session.get("user")
    return int(user["id"]) if user else None


def _err(message, code=400):
    return jsonify({"error": message}), code


@poker_bp.before_request
def _poker_csrf_guard():
    # изменяющие запросы — только из нашей страницы (кастомный заголовок не подделать чужой формой)
    if request.method in ("POST", "DELETE") and request.path.startswith("/poker/"):
        if request.headers.get("X-Requested-With") != "poker":
            abort(403)
        if (request.content_length or 0) > MAX_REQUEST_BYTES:
            abort(413)


def _process_image(file) -> bytes:
    """Проверяет картинку, обрезает под пропорции карты и сжимает в WebP."""
    raw = file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Файл больше 6 МБ")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        raise ValueError("Файл не похож на картинку")
    img = ImageOps.exif_transpose(img).convert("RGBA")
    img = ImageOps.fit(img, CARD_SIZE, Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, "WEBP", quality=85)
    return out.getvalue()


def _upload(images: dict[str, bytes]) -> dict[str, str] | None:
    """Загружает части скина в S3: {часть: ключ}. При ошибке удаляет уже загруженное."""
    global _bucket_ready
    if not _bucket_ready:
        _bucket_ready = skins_s3_client.ensure_bucket()
    folder = uuid.uuid4().hex
    keys = {}
    for part, data in images.items():
        key = f"{folder}/{part}.webp"
        if not skins_s3_client.upload_file(data, key, content_type="image/webp"):
            _remove_files(keys.values())
            return None
        keys[part] = key
    return keys


def _remove_files(keys):
    for key in keys:
        skins_s3_client.delete_file(key)
        with _img_cache_lock:
            _img_cache.pop(key, None)


def _skin_keys(skin: dict) -> list[str]:
    data = skin["data"]
    return [data["image"]] if skin["kind"] == "back" else list(data.get("images", {}).values())


def _skin_row(sk: dict, owned: set, selected: dict) -> dict:
    key = str(sk["id"])
    return {
        "id": sk["id"], "key": key, "kind": sk["kind"], "name": sk["name"], "price": sk["price"],
        "is_active": sk["is_active"], "private": sk["owner_tg_id"] is not None, "owner_tg_id": sk["owner_tg_id"],
        "owned": sk["id"] in owned or (sk["price"] == 0 and sk["owner_tg_id"] is None),
        "selected": selected.get(sk["kind"]) == key,
        "desc": table.skin_desc(key, sk["kind"]),
    }


# ---------- картинки ----------
@poker_bp.route("/poker/skin_img/<int:skin_id>/<part>")
def skin_image(skin_id: int, part: str):
    with table.lock:
        sk = table.skins.get(skin_id)
    if not sk:
        abort(404)
    key = sk["data"].get("image") if part == "back" and sk["kind"] == "back" else sk["data"].get("images", {}).get(part)
    if not key:
        abort(404)
    with _img_cache_lock:
        data = _img_cache.get(key)
        if data:
            _img_cache.move_to_end(key)
    if data is None:
        data = skins_s3_client.download_file(key)
        if data is None:
            abort(404)
        with _img_cache_lock:
            _img_cache[key] = data
            while len(_img_cache) > 400:
                _img_cache.popitem(last=False)
    return Response(data, mimetype="image/webp", headers={"Cache-Control": "public, max-age=604800, immutable"})


# ---------- магазин ----------
@poker_bp.route("/poker/skins")
def skins_catalog():
    tg_id = _tg_id()
    admin = is_admin(tg_id)
    with table.lock:
        table.connect_profile(tg_id)
        owned = get_owned_skin_ids(tg_id) if tg_id else set()
        profile = table.profiles.get(tg_id) or {}
        selected = {"front": str(profile.get("front_skin", "classic")), "back": str(profile.get("back_skin", "classic"))}
        rows = [
            _skin_row(sk, owned, selected) for sk in table.skins.values()
            if admin or (sk["owner_tg_id"] is None and sk["is_active"]) or sk["id"] in owned
        ]
        player = table.player_of(tg_id) if tg_id else None
        chips = player.stack if player else profile.get("chips")
        return jsonify({
            "std": [{"key": k, "name": v} for k, v in STD_SKINS.items()],
            "skins": rows, "selected": selected, "logged_in": tg_id is not None, "is_admin": admin,
            "chips": chips, "custom_back_price": table.cfg["custom_back_price"],
        })


@poker_bp.route("/poker/skins/select", methods=["POST"])
def skins_select():
    tg_id = _tg_id()
    if tg_id is None:
        return _err("Войдите через Telegram", 401)
    body = request.get_json(silent=True) or {}
    with table.lock:
        error = table.select_skin(tg_id, body.get("kind"), str(body.get("key")))
        if error:
            return _err(error)
        table.broadcast()
    return jsonify({"ok": True})


@poker_bp.route("/poker/skins/buy", methods=["POST"])
def skins_buy():
    tg_id = _tg_id()
    if tg_id is None:
        return _err("Войдите через Telegram", 401)
    body = request.get_json(silent=True) or {}
    try:
        skin_id = int(body.get("skin_id"))
    except (TypeError, ValueError):
        return _err("Нет такого скина")
    with table.lock:
        error = table.buy(tg_id, skin_id)
        if error:
            return _err(error)
        sk = table.skins[skin_id]
        table.select_skin(tg_id, sk["kind"], str(skin_id))
        table.broadcast()
    return jsonify({"ok": True})


@poker_bp.route("/poker/skins/upload_back", methods=["POST"])
def skins_upload_back():
    """Игрок загружает свой задник за фишки: его видят все, выбрать может только он."""
    tg_id = _tg_id()
    if tg_id is None:
        return _err("Войдите через Telegram", 401)
    name = (request.form.get("name") or "Мой задник").strip()[:60]
    file = request.files.get("image")
    if not file:
        return _err("Выберите картинку")
    try:
        image = _process_image(file)
    except ValueError as e:
        return _err(str(e))
    with table.lock:
        price = table.cfg["custom_back_price"]
        error = table.charge(tg_id, price)  # сначала списываем, при сбое вернём
    if error:
        return _err(error)
    keys = _upload({"back": image})
    with table.lock:
        if keys is None:
            table.refund(tg_id, price)
            table.broadcast()
            return _err("Не удалось сохранить картинку, фишки возвращены", 500)
        sk = create_skin("back", name, 0, {"image": keys["back"]}, owner_tg_id=tg_id)
        table.reload_skins()
        table.select_skin(tg_id, "back", str(sk["id"]))
        table.broadcast()
    return jsonify({"ok": True, "id": sk["id"]})


# ---------- админка: скины ----------
def _require_admin():
    if not is_admin(_tg_id()):
        abort(403)


@poker_bp.route("/poker/admin/skins", methods=["POST"])
def admin_create_skin():
    """
    multipart: kind=front|back, name, price;
      back  — image;
      front — bg, color_s/h/d/c, rank_A ... rank_2 (картинки рангов, любые — необязательны).
    """
    _require_admin()
    form = request.form
    kind = form.get("kind")
    name = (form.get("name") or "").strip()[:60]
    if kind not in ("front", "back") or not name:
        return _err("Укажите тип и название")
    try:
        price = max(0, int(form.get("price") or 0))
    except ValueError:
        return _err("Цена — целое число")
    images = {}
    try:
        if kind == "back":
            if not request.files.get("image"):
                return _err("Нужна картинка задника")
            images["back"] = _process_image(request.files["image"])
        else:
            for r in RANKS:
                f = request.files.get(f"rank_{r}")
                if f and f.filename:
                    images[r] = _process_image(f)
    except ValueError as e:
        return _err(str(e))
    data = {}
    if kind == "front":
        colors = {su: form.get(f"color_{su}", "") for su in SUITS}
        bg = form.get("bg", "#ffffff")
        if not all(HEX_COLOR.match(c) for c in [*colors.values(), bg]):
            return _err("Цвета — в формате #rrggbb")
        data = {"colors": colors, "bg": bg, "images": {}}
    keys = _upload(images) if images else {}
    if keys is None:
        return _err("Не удалось загрузить картинки в S3", 500)
    if kind == "back":
        data = {"image": keys["back"]}
    else:
        data["images"] = keys
    sk = create_skin(kind, name, price, data)
    with table.lock:
        table.reload_skins()
        table.broadcast()
    return jsonify({"ok": True, "id": sk["id"]})


@poker_bp.route("/poker/admin/skins/<int:skin_id>", methods=["POST", "DELETE"])
def admin_edit_skin(skin_id: int):
    _require_admin()
    if request.method == "DELETE":
        sk = delete_skin(skin_id)
        if not sk:
            return _err("Нет такого скина", 404)
        _remove_files(_skin_keys(sk))
        with table.lock:
            for profile in table.profiles.values():  # у кого был выбран — классика
                for kind in ("front", "back"):
                    if str(profile.get(f"{kind}_skin")) == str(skin_id):
                        profile[f"{kind}_skin"] = "classic"
            for p in table.players:
                if p.back_skin == str(skin_id):
                    p.back_skin = "classic"
            table.reload_skins()
            table.broadcast()
        return jsonify({"ok": True})
    body = request.get_json(silent=True) or {}
    fields = {}
    if "name" in body:
        fields["name"] = str(body["name"]).strip()[:60] or None
    if "price" in body:
        try:
            fields["price"] = max(0, int(body["price"]))
        except (TypeError, ValueError):
            return _err("Цена — целое число")
    if "is_active" in body:
        fields["is_active"] = bool(body["is_active"])
    if not update_skin(skin_id, **fields):
        return _err("Нет такого скина", 404)
    with table.lock:
        table.reload_skins()
    return jsonify({"ok": True})


# ---------- админка: настройки и фишки ----------
@poker_bp.route("/poker/admin/settings", methods=["GET", "POST"])
def admin_settings():
    _require_admin()
    with table.lock:
        if request.method == "POST":
            error = table.update_settings((request.get_json(silent=True) or {}).get("values"))
            if error:
                return _err(error)
            table.broadcast()
        return jsonify({
            "spec": [{"key": k, "default": v[0], "min": v[1], "max": v[2], "label": v[3]} for k, v in SETTINGS_SPEC.items()],
            "active": table.cfg, "pending": table.pending_cfg,
        })


# ---------- админка: список пользователей (имя и аватар — из Telegram, с кэшем) ----------
USER_INFO_TTL = 3600
_user_info: dict[int, dict] = {}       # tg_id -> {username, first_name, at}
_avatars: dict[int, tuple] = {}        # tg_id -> (bytes | None, at)
_info_lock = Lock()
_warming = False


def _fetch_user_info(tg_id: int) -> dict:
    try:
        u = bot.get_chat_member(TELEGRAM_CHAT_ID, tg_id).user
        info = {"username": u.username or "", "first_name": " ".join(filter(None, [u.first_name, u.last_name]))}
    except Exception:
        info = {"username": "", "first_name": ""}
    info["at"] = time.time()
    return info


def _warm_user_info(ids):
    """Фоново подтягивает имена всех пользователей (запросов к Telegram много — не держим запрос админа)."""
    global _warming
    try:
        for tg_id in ids:
            with _info_lock:
                fresh = tg_id in _user_info and time.time() - _user_info[tg_id]["at"] < USER_INFO_TTL
            if not fresh:
                info = _fetch_user_info(tg_id)
                with _info_lock:
                    _user_info[tg_id] = info
    finally:
        _warming = False


@poker_bp.route("/poker/admin/users")
def admin_users():
    """Пользователи с фишками; q — поиск по id, username или имени."""
    global _warming
    _require_admin()
    q = (request.args.get("q") or "").strip().lower().lstrip("@")
    rows = list_users_chips()
    with _info_lock:
        stale = [t for t, _ in rows if t not in _user_info or time.time() - _user_info[t]["at"] >= USER_INFO_TTL]
        info = dict(_user_info)
    if stale and not _warming:
        _warming = True
        socketio.start_background_task(_warm_user_info, stale)
    with table.lock:
        seated = {p.tg_id: p.stack for p in table.players}
    users = []
    for tg_id, chips in rows:
        i = info.get(tg_id, {})
        hay = f"{tg_id} {i.get('username', '')} {i.get('first_name', '')}".lower()
        if q and q not in hay:
            continue
        users.append({
            "tg_id": str(tg_id), "username": i.get("username", ""), "first_name": i.get("first_name", ""),
            "chips": seated.get(tg_id, chips), "seated": tg_id in seated,
            "avatar": f"/poker/admin/avatar/{tg_id}",
        })
    users.sort(key=lambda u: -u["chips"])
    return jsonify({"users": users[:60], "total": len(users), "loading": bool(stale)})


@poker_bp.route("/poker/admin/avatar/<int:tg_id>")
def admin_avatar(tg_id: int):
    _require_admin()
    with _info_lock:
        cached = _avatars.get(tg_id)
    if cached is None or time.time() - cached[1] >= USER_INFO_TTL:
        data = None
        try:
            photos = bot.get_user_profile_photos(tg_id, limit=1).photos
            if photos:
                data = bot.download_file(bot.get_file(photos[0][0].file_id).file_path)  # самый маленький размер
        except Exception:
            data = None
        cached = (data, time.time())
        with _info_lock:
            _avatars[tg_id] = cached
    if not cached[0]:
        abort(404)
    return Response(cached[0], mimetype="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@poker_bp.route("/poker/admin/chips", methods=["POST"])
def admin_chips():
    _require_admin()
    body = request.get_json(silent=True) or {}
    try:
        tg_id, amount = int(body.get("tg_id")), int(body.get("amount"))
    except (TypeError, ValueError):
        return _err("tg_id и сумма — целые числа")
    with table.lock:
        new = table.give_chips(tg_id, amount)
        if new is None:
            return _err("Пользователь не найден", 404)
        table.broadcast()
    return jsonify({"ok": True, "chips": new})
