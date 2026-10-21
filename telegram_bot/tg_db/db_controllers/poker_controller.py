import json
from ..import session_scope
from ..models.tg_user import TelegramUser
from ..models.poker import PokerSkin, PokerSkinOwner, PokerSetting
from ..models.photo import Photo
from sqlalchemy import func


def get_poker_profile(tg_id: int) -> dict | None:
    with session_scope() as session:
        user = session.query(TelegramUser).filter_by(tg_id=tg_id).first()
        if user is None:
            return None
        return {
            "chips": user.chips,
            "front_skin": user.poker_card_style,
            "back_skin": user.poker_back_skin,
            "bonus_at": user.poker_bonus_at,
        }


def set_chips_many(chips_by_tg_id: dict[int, int]):
    """Сохраняет стеки нескольких игроков одной транзакцией."""
    if not chips_by_tg_id:
        return
    with session_scope() as session:
        users = session.query(TelegramUser).filter(TelegramUser.tg_id.in_(chips_by_tg_id.keys())).all()
        for user in users:
            user.chips = max(0, int(chips_by_tg_id[user.tg_id]))


def add_chips(tg_id: int, amount: int) -> int | None:
    """Начисляет (или списывает, если amount < 0) фишки в БД. Возвращает новый баланс."""
    with session_scope() as session:
        user = session.query(TelegramUser).filter_by(tg_id=tg_id).with_for_update().first()
        if user is None:
            return None
        user.chips = max(0, user.chips + amount)
        return user.chips


def set_skin_choice(tg_id: int, kind: str, key: str) -> bool:
    with session_scope() as session:
        user = session.query(TelegramUser).filter_by(tg_id=tg_id).first()
        if user is None:
            return False
        if kind == "front":
            user.poker_card_style = key
        else:
            user.poker_back_skin = key
        return True


def claim_bonus(tg_id: int, amount: int, cooldown: float, now: float, add_to_chips: bool = True) -> dict | None:
    """
    Выдаёт бонус, если откат прошёл. Возвращает {"chips", "bonus_at"} или None, если рано.
    add_to_chips=False — только сдвинуть откат (фишки добавит стол, игрок сидит за ним).
    """
    with session_scope() as session:
        user = session.query(TelegramUser).filter_by(tg_id=tg_id).with_for_update().first()
        if user is None or now < (user.poker_bonus_at or 0):
            return None
        user.poker_bonus_at = now + cooldown
        if add_to_chips:
            user.chips += amount
        return {"chips": user.chips, "bonus_at": user.poker_bonus_at}


# ---------- скины ----------
def _skin_dict(skin: PokerSkin) -> dict:
    return {
        "id": skin.id, "kind": skin.kind, "name": skin.name, "price": skin.price,
        "owner_tg_id": skin.owner_tg_id, "is_active": skin.is_active, "data": json.loads(skin.data),
    }


def get_all_skins() -> list[dict]:
    with session_scope() as session:
        return [_skin_dict(s) for s in session.query(PokerSkin).order_by(PokerSkin.id).all()]


def get_owned_skin_ids(tg_id: int) -> set[int]:
    with session_scope() as session:
        return {o.skin_id for o in session.query(PokerSkinOwner).filter_by(tg_id=tg_id).all()}


def create_skin(kind: str, name: str, price: int, data: dict, owner_tg_id: int | None = None) -> dict:
    """Создаёт скин; личный (owner_tg_id) сразу принадлежит загрузившему."""
    with session_scope() as session:
        skin = PokerSkin(kind=kind, name=name, price=price, data=json.dumps(data), owner_tg_id=owner_tg_id)
        session.add(skin)
        session.flush()
        if owner_tg_id is not None:
            session.add(PokerSkinOwner(tg_id=owner_tg_id, skin_id=skin.id))
        return _skin_dict(skin)


def update_skin(skin_id: int, **fields) -> dict | None:
    with session_scope() as session:
        skin = session.get(PokerSkin, skin_id)
        if skin is None:
            return None
        for k in ("name", "price", "is_active"):
            if k in fields and fields[k] is not None:
                setattr(skin, k, fields[k])
        return _skin_dict(skin)


def delete_skin(skin_id: int) -> dict | None:
    """Удаляет скин; у кого он был выбран — возвращается классика. Возвращает удалённый скин (для чистки S3)."""
    with session_scope() as session:
        skin = session.get(PokerSkin, skin_id)
        if skin is None:
            return None
        result = _skin_dict(skin)
        column = TelegramUser.poker_card_style if skin.kind == "front" else TelegramUser.poker_back_skin
        session.query(TelegramUser).filter(column == str(skin_id)).update({column: "classic"}, synchronize_session=False)
        session.query(PokerSkinOwner).filter_by(skin_id=skin_id).delete()
        session.delete(skin)
        return result


def buy_skin(tg_id: int, skin_id: int, price: int, charge_db: bool) -> str | None:
    """
    Покупка в одной транзакции: проверка, списание (если charge_db) и выдача скина.
    charge_db=False — фишки списывает стол (игрок сидит за ним).
    """
    with session_scope() as session:
        if session.query(PokerSkinOwner).filter_by(tg_id=tg_id, skin_id=skin_id).first():
            return "Скин уже куплен"
        if charge_db:
            user = session.query(TelegramUser).filter_by(tg_id=tg_id).with_for_update().first()
            if user is None or user.chips < price:
                return "Недостаточно фишек"
            user.chips -= price
        session.add(PokerSkinOwner(tg_id=tg_id, skin_id=skin_id))
        return None


# ---------- настройки ----------
def get_settings() -> dict[str, int]:
    with session_scope() as session:
        return {s.key: s.value for s in session.query(PokerSetting).all()}


def save_settings(values: dict[str, int]):
    with session_scope() as session:
        for key, value in values.items():
            row = session.get(PokerSetting, key)
            if row:
                row.value = value
            else:
                session.add(PokerSetting(key=key, value=value))


def list_users_chips() -> list[tuple[int, int]]:
    """Все пользователи и их фишки (для админки)."""
    with session_scope() as session:
        return [(u.tg_id, u.chips) for u in session.query(TelegramUser.tg_id, TelegramUser.chips).all()]


def random_gallery_photo_ids(count: int) -> list[int]:
    """Случайные фото из галереи (только отсортированные по категориям) — для задника «случайное фото»."""
    if count <= 0:
        return []
    with session_scope() as session:
        rows = (session.query(Photo.id).filter(Photo.category_id.is_not(None))
                .order_by(func.random()).limit(count).all())
        return [r[0] for r in rows]
