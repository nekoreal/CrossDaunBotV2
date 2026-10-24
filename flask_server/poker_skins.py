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
from telegram_bot.tg_db.db_controllers.photo_controller import get_photo_by_id
from telegram_bot.tg_db.db_controllers.user_controller import find_user_by_tg_id
from flask_server.dashboard import socketio
from flask_server.poker import poker_bp, table, is_admin, STD_SKINS, SETTINGS_SPEC, IMMEDIATE_SETTINGS

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
    if skin["kind"] == "back":
        return [data["image"]] if "image" in data else []
    return list(data.get("images", {}).values())


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


# ---------- фото из галереи: источник для скинов и задник «случайное фото» ----------
_gallery_cache: "OrderedDict[str, bytes]" = OrderedDict()


def gallery_photo_bytes(photo_id: int, card: bool) -> bytes | None:
    """card — обрезано под карту (задник), иначе — уменьшенное целиком (для редактора скинов). С кэшем."""
    key = f"{photo_id}:{int(card)}"
    with _img_cache_lock:
        data = _gallery_cache.get(key)
        if data:
            _gallery_cache.move_to_end(key)
            return data
    photo = get_photo_by_id(photo_id)
    if not photo:
        return None
    try:
        img = Image.open(io.BytesIO(photo["file_bytes"]))
        img.draft("RGB", (CARD_SIZE[0] * 2, CARD_SIZE[1] * 2) if card else (1400, 1400))  # JPEG декодируется сразу уменьшенным
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        return None
    if card:
        img = ImageOps.fit(img, CARD_SIZE, Image.Resampling.LANCZOS)
    else:
        img.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, "WEBP", quality=82, method=4)
    data = out.getvalue()
    with _img_cache_lock:
        _gallery_cache[key] = data
        while len(_gallery_cache) > 300:
            _gallery_cache.popitem(last=False)
    return data


def _prefetch_gallery(ids):
    for photo_id in ids:
        try:
            gallery_photo_bytes(photo_id, True)
        except Exception as e:
            print(f"Покер: не удалось подготовить фото {photo_id}: {e}")


table.prefetch_gallery = lambda ids: socketio.start_background_task(_prefetch_gallery, list(ids))


@poker_bp.route("/poker/gallery_photo/<int:photo_id>")
def gallery_photo(photo_id: int):
    data = gallery_photo_bytes(photo_id, request.args.get("card") == "1")
    if data is None:
        abort(404)
    return Response(data, mimetype="image/webp", headers={"Cache-Control": "public, max-age=604800"})


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
    """
    Игрок загружает свой задник за фишки: его видят все, выбрать может только он.
    Свой задник у человека один — новая загрузка заменяет старый (картинка меняется, задник остаётся выбранным).
    """
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
        own = sorted((sk for sk in table.skins.values() if sk["kind"] == "back" and sk["owner_tg_id"] == tg_id),
                     key=lambda sk: sk["id"], reverse=True)
        if own:
            sk, extra = own[0], own[1:]
            old_files = _skin_keys(sk)
            update_skin(sk["id"], name=name, data={"image": keys["back"]})
        else:
            sk, extra, old_files = create_skin("back", name, 0, {"image": keys["back"]}, owner_tg_id=tg_id), [], []
        for x in extra:  # если раньше успели накопиться несколько — оставляем один
            delete_skin(x["id"])
            old_files += _skin_keys(x)
            for p in table.players:
                if p.back_skin == str(x["id"]):
                    p.back_skin = "classic"
        table.reload_skins()
        table.select_skin(tg_id, "back", str(sk["id"]))
        table.broadcast()
    _remove_files(old_files)
    return jsonify({"ok": True, "id": sk["id"], "replaced": bool(own)})


# ---------- админка: скины ----------
def _require_admin():
    if not is_admin(_tg_id()):
        abort(403)


def _skin_form(kind: str):
    """
    Общая часть создания и редактирования (multipart): name, price;
      back  — image; front — bg, color_s/h/d/c, rank_A ... rank_2 (картинки рангов — необязательны).
    Возвращает (поля, картинки {часть: webp}) или строку ошибки.
    """
    form = request.form
    name = (form.get("name") or "").strip()[:60]
    if not name:
        return "Укажите название"
    try:
        price = max(0, int(form.get("price") or 0))
    except ValueError:
        return "Цена — целое число"
    images = {}
    try:
        if kind == "back":
            if request.files.get("image"):
                images["back"] = _process_image(request.files["image"])
        else:
            for r in RANKS:
                f = request.files.get(f"rank_{r}")
                if f and f.filename:
                    images[r] = _process_image(f)
    except ValueError as e:
        return str(e)
    fields = {"name": name, "price": price}
    if kind == "front":
        colors = {su: form.get(f"color_{su}", "") for su in SUITS}
        bg = form.get("bg", "#ffffff")
        if not all(HEX_COLOR.match(c) for c in [*colors.values(), bg]):
            return "Цвета — в формате #rrggbb"
        fields.update(colors=colors, bg=bg)
    return fields, images


@poker_bp.route("/poker/admin/skins", methods=["POST"])
def admin_create_skin():
    _require_admin()
    kind = request.form.get("kind")
    if kind not in ("front", "back"):
        return _err("Неизвестный тип скина")
    parsed = _skin_form(kind)
    if isinstance(parsed, str):
        return _err(parsed)
    fields, images = parsed
    if kind == "back" and "back" not in images:
        return _err("Нужна картинка задника")
    keys = _upload(images) if images else {}
    if keys is None:
        return _err("Не удалось загрузить картинки в S3", 500)
    if kind == "back":
        data = {"image": keys["back"]}
    else:
        data = {"colors": fields["colors"], "bg": fields["bg"], "images": keys}
    sk = create_skin(kind, fields["name"], fields["price"], data)
    with table.lock:
        table.reload_skins()
        table.broadcast()
    return jsonify({"ok": True, "id": sk["id"]})


@poker_bp.route("/poker/admin/skins/<int:skin_id>/edit", methods=["POST"])
def admin_edit_skin_full(skin_id: int):
    """
    Редактирование скина: те же поля, что при создании; keep — части через запятую, картинки которых
    не менялись (остальные либо пришли новыми файлами, либо удалены).
    """
    _require_admin()
    with table.lock:
        sk = table.skins.get(skin_id)
        gallery = table.is_gallery_back(skin_id)
    if not sk:
        return _err("Нет такого скина", 404)
    if gallery:
        return _err("У случайного задника из галереи меняется только цена")
    parsed = _skin_form(sk["kind"])
    if isinstance(parsed, str):
        return _err(parsed)
    fields, images = parsed
    keep = {x for x in (request.form.get("keep") or "").split(",") if x}
    old_parts = {"back": sk["data"]["image"]} if sk["kind"] == "back" else dict(sk["data"].get("images", {}))
    kept = {part: key for part, key in old_parts.items() if part in keep and part not in images}
    if sk["kind"] == "back" and not kept and "back" not in images:
        return _err("Нужна картинка задника")
    uploaded = _upload(images) if images else {}
    if uploaded is None:
        return _err("Не удалось загрузить картинки в S3", 500)
    parts = {**kept, **uploaded}
    data = {"image": parts["back"]} if sk["kind"] == "back" else {"colors": fields["colors"], "bg": fields["bg"], "images": parts}
    # у личного задника игрока цены нет
    price = 0 if sk["owner_tg_id"] is not None else fields["price"]
    if not update_skin(skin_id, name=fields["name"], price=price, data=data):
        _remove_files(uploaded.values())
        return _err("Нет такого скина", 404)
    _remove_files([key for part, key in old_parts.items() if part not in kept])  # заменённые и удалённые
    with table.lock:
        table.reload_skins()
        table.broadcast()
    return jsonify({"ok": True})


@poker_bp.route("/poker/admin/skins/<int:skin_id>", methods=["POST", "DELETE"])
def admin_edit_skin(skin_id: int):
    _require_admin()
    if request.method == "DELETE":
        with table.lock:
            if table.is_gallery_back(skin_id):
                return _err("Системный скин нельзя удалить — можно скрыть или поменять цену")
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
                for kind in ("front", "back"):
                    if getattr(p, f"{kind}_skin") == str(skin_id):
                        setattr(p, f"{kind}_skin", "classic")
            table.reload_skins()
            table.broadcast()
        return jsonify({"ok": True})
    body = request.get_json(silent=True) or {}
    with table.lock:
        if table.is_gallery_back(skin_id):  # системный: только цена
            body = {k: v for k, v in body.items() if k == "price"}
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
            # цена своего задника — во вкладке «Скины»
            "spec": [{"key": k, "default": v[0], "min": v[1], "max": v[2], "label": v[3]}
                     for k, v in SETTINGS_SPEC.items() if k not in IMMEDIATE_SETTINGS],
            "active": table.cfg, "pending": table.pending_cfg,
            "custom_back_price": table.cfg["custom_back_price"],
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


def user_infos(ids) -> tuple[dict[int, dict], bool]:
    """Имена из кэша по tg_id; устаревшие подтягиваются в фоне. Второе значение — идёт ли подгрузка."""
    global _warming
    with _info_lock:
        stale = [t for t in ids if t not in _user_info or time.time() - _user_info[t]["at"] >= USER_INFO_TTL]
        info = dict(_user_info)
    if stale and not _warming:
        _warming = True
        socketio.start_background_task(_warm_user_info, stale)
    return info, bool(stale)


def _users_with_names(rows):
    """Добавляет к (tg_id, фишки) имена из кэша; устаревшие подтягиваются в фоне."""
    info, loading = user_infos([t for t, _ in rows])
    with table.lock:
        seated = {p.tg_id: p.stack for p in table.players}  # у сидящих за столом — актуальный стек
    users = []
    for tg_id, chips in rows:
        i = info.get(tg_id, {})
        users.append({
            "tg_id": str(tg_id), "username": i.get("username", ""), "first_name": i.get("first_name", ""),
            "chips": seated.get(tg_id, chips), "seated": tg_id in seated, "avatar": f"/poker/avatar/{tg_id}",
        })
    users.sort(key=lambda u: -u["chips"])
    return users, loading


@poker_bp.route("/poker/admin/users")
def admin_users():
    """Пользователи с фишками; q — поиск по id, username или имени."""
    _require_admin()
    q = (request.args.get("q") or "").strip().lower().lstrip("@")
    users, loading = _users_with_names(list_users_chips())
    if q:
        users = [u for u in users if q in f"{u['tg_id']} {u['username']} {u['first_name']}".lower()]
    return jsonify({"users": users[:60], "total": len(users), "loading": loading})


@poker_bp.route("/poker/leaderboard")
def leaderboard():
    """Топ по фишкам — видно всем."""
    users, loading = _users_with_names(list_users_chips())
    me = _tg_id()
    place = next((i + 1 for i, u in enumerate(users) if u["tg_id"] == str(me)), None)
    return jsonify({"users": users[:50], "total": len(users), "loading": loading, "me": str(me) if me else None, "my_place": place})


@poker_bp.route("/poker/avatar/<int:tg_id>")
def avatar(tg_id: int):
    with _info_lock:
        cached = _avatars.get(tg_id)
    if cached is None or time.time() - cached[1] >= USER_INFO_TTL:
        if cached is None and not find_user_by_tg_id(tg_id):
            abort(404)  # только участники сообщества — не дёргаем Telegram ради любых id
        data = None
        try:
            photos = bot.get_user_profile_photos(tg_id, limit=1).photos
            if photos:
                raw = bot.download_file(bot.get_file(photos[0][0].file_id).file_path)  # самый маленький размер
                img = ImageOps.fit(ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB"), (96, 96), Image.Resampling.LANCZOS)
                out = io.BytesIO()
                img.save(out, "WEBP", quality=80)
                data = out.getvalue()  # ~3 КБ вместо ~15 КБ jpeg
        except Exception:
            data = None
        cached = (data, time.time())
        with _info_lock:
            _avatars[tg_id] = cached
    if not cached[0]:
        abort(404)
    return Response(cached[0], mimetype="image/webp", headers={"Cache-Control": "public, max-age=86400"})


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
