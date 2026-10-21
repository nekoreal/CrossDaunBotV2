from ..import session_scope
from ..models.tg_user import TelegramUser


def get_poker_profile(tg_id: int) -> dict | None:
    with session_scope() as session:
        user = session.query(TelegramUser).filter_by(tg_id=tg_id).first()
        if user is None:
            return None
        return {
            "chips": user.chips,
            "card_style": user.poker_card_style,
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


def set_card_style(tg_id: int, card_style: str) -> bool:
    with session_scope() as session:
        user = session.query(TelegramUser).filter_by(tg_id=tg_id).first()
        if user is None:
            return False
        user.poker_card_style = card_style
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
