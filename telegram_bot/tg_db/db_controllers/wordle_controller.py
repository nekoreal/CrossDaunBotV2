import json
from datetime import date, datetime, timezone
from sqlalchemy.exc import IntegrityError
from ..import session_scope
from ..models.wordle import WordleGame


def _game_dict(game: WordleGame) -> dict:
    return {
        "tg_id": game.tg_id, "day": game.day, "guesses": json.loads(game.guesses),
        "solved": game.solved, "finished": game.finished, "finished_at": game.finished_at,
    }


def get_game(tg_id: int, day: date) -> dict | None:
    with session_scope() as session:
        game = session.query(WordleGame).filter_by(tg_id=tg_id, day=day).first()
        return _game_dict(game) if game else None


def add_guess(tg_id: int, day: date, guess: str, answer: str, max_tries: int) -> tuple[dict | None, str | None]:
    """
    Добавляет попытку в одной транзакции (строка блокируется — двойной клик не даст лишнюю попытку).
    Возвращает (партия, ошибка); в партии just_solved=True, если именно эта попытка угадала слово.
    """
    try:
        with session_scope() as session:
            if not session.query(WordleGame.id).filter_by(tg_id=tg_id, day=day).first():
                session.add(WordleGame(tg_id=tg_id, day=day, guesses="[]"))
                session.flush()
    except IntegrityError:
        pass  # партию только что создал параллельный запрос
    with session_scope() as session:
        game = session.query(WordleGame).filter_by(tg_id=tg_id, day=day).with_for_update().first()
        if game.finished:
            return None, "Сегодняшнее слово уже сыграно"
        guesses = json.loads(game.guesses) + [guess]
        game.guesses = json.dumps(guesses)
        if guess == answer or len(guesses) >= max_tries:
            game.solved = guess == answer
            game.finished = True
            game.finished_at = datetime.now(timezone.utc)
        result = _game_dict(game)
        result["just_solved"] = game.solved
        return result, None


def games_of_day(day: date) -> list[dict]:
    with session_scope() as session:
        rows = session.query(WordleGame).filter_by(day=day).order_by(WordleGame.finished_at.is_(None), WordleGame.finished_at).all()
        return [_game_dict(g) for g in rows]


def all_results() -> list[tuple[int, date, bool]]:
    """Все законченные партии (tg_id, день, угадал) — для стриков и лидерборда."""
    with session_scope() as session:
        rows = session.query(WordleGame.tg_id, WordleGame.day, WordleGame.solved).filter_by(finished=True).all()
        return [(r[0], r[1], r[2]) for r in rows]
