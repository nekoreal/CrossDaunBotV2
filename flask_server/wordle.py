import random
import secrets
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock
from flask import Blueprint, request, session, render_template, jsonify
from pytz import timezone

from telegram_bot.tg_db.db_controllers.poker_controller import get_poker_profile
from telegram_bot.tg_db.db_controllers.wordle_controller import get_game, add_guess, games_of_day, all_results
from flask_server.poker import table
from flask_server.poker_skins import user_infos

TZ = timezone("Europe/Moscow")   # день меняется в полночь по Москве — как у планировщика
MAX_TRIES = 6
REWARD = 500                     # фишки покера за угаданное слово дня
EPOCH = date(2026, 1, 1)         # от этой даты считается номер слова дня
PRACTICE_TTL = 24 * 3600

_words_dir = Path(__file__).parent / "wordle_words"
ANSWERS = [w.strip() for w in (_words_dir / "answers.txt").read_text().split() if len(w.strip()) == 5]
ALLOWED = set(ANSWERS) | {w.strip() for w in (_words_dir / "allowed.txt").read_text().split()}
_daily_order = ANSWERS[:]
random.Random("crossdaun-wordle").shuffle(_daily_order)  # фиксированный порядок: слово дня одно у всех и не меняется после рестарта

_practice: dict[str, dict] = {}  # токен из сессии -> {"word", "guesses", "at"}; тренировка без наград, БД не нужна
_practice_lock = Lock()

wordle_bp = Blueprint("wordle_bp", __name__)


def today() -> date:
    return datetime.now(TZ).date()


def daily_word(day: date) -> str:
    return _daily_order[(day - EPOCH).days % len(_daily_order)]


def score(guess: str, answer: str) -> str:
    """Подсветка попытки: g — на месте, y — есть в слове, b — нет (повторные буквы считаются честно)."""
    marks = ["b"] * 5
    left = {}
    for i, (g, a) in enumerate(zip(guess, answer)):
        if g == a:
            marks[i] = "g"
        else:
            left[a] = left.get(a, 0) + 1
    for i, g in enumerate(guess):
        if marks[i] == "b" and left.get(g, 0) > 0:
            marks[i] = "y"
            left[g] -= 1
    return "".join(marks)


def _tg_id():
    user = session.get("user")
    return int(user["id"]) if user else None


def _err(message, code=400):
    return jsonify({"error": message}), code


def _read_guess() -> tuple[str | None, str | None]:
    word = str((request.get_json(silent=True) or {}).get("word", "")).strip().lower()
    if len(word) != 5 or not word.isalpha():
        return None, "Нужно слово из 5 букв"
    if word not in ALLOWED:
        return None, "Такого слова нет в словаре"
    return word, None


def _chips(tg_id) -> int | None:
    with table.lock:
        p = table.player_of(tg_id)
        if p:
            return p.stack
    profile = get_poker_profile(tg_id)
    return profile["chips"] if profile else None


def streaks(days: set[date], day: date, failed_today: bool = False) -> tuple[int, int]:
    """
    (текущий стрик, лучший) по дням с угаданным словом.
    Текущий жив, если угадано сегодня или вчера (сегодня ещё можно сыграть); пропуск дня или промах его обнуляют.
    """
    cur = 0
    d = day if day in days or failed_today else day - timedelta(days=1)
    while d in days:
        cur += 1
        d -= timedelta(days=1)
    best = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return cur, best


def _stats() -> dict[int, dict]:
    day = today()
    by_user: dict[int, dict] = {}
    for tg_id, d, solved in all_results():
        s = by_user.setdefault(tg_id, {"played": 0, "wins": 0, "days": set(), "failed_today": False})
        s["played"] += 1
        if solved:
            s["wins"] += 1
            s["days"].add(d)
        elif d == day:
            s["failed_today"] = True
    for s in by_user.values():
        s["streak"], s["max_streak"] = streaks(s.pop("days"), day, s.pop("failed_today"))
    return by_user


def _next_day_at() -> float:
    tomorrow = today() + timedelta(days=1)
    return TZ.localize(datetime(tomorrow.year, tomorrow.month, tomorrow.day)).timestamp()


def _daily_state(tg_id) -> dict:
    day = today()
    answer = daily_word(day)
    game = get_game(tg_id, day) if tg_id else None
    guesses = game["guesses"] if game else []
    finished = bool(game and game["finished"])
    state = {
        "mode": "daily", "day": day.isoformat(), "number": (day - EPOCH).days + 1,
        "logged_in": tg_id is not None, "max_tries": MAX_TRIES, "reward": REWARD,
        "rows": [{"word": w, "marks": score(w, answer)} for w in guesses],
        "finished": finished, "solved": bool(game and game["solved"]),
        "answer": answer if finished else None,  # слово уходит клиенту только после конца партии
        "next_at": _next_day_at(), "server_now": time.time(),
    }
    if tg_id:
        stats = _stats().get(tg_id, {})
        state["streak"] = stats.get("streak", 0)
        state["chips"] = _chips(tg_id)
    return state


def games_summary(tg_id) -> dict:
    """Живые статусы для панели игр на главной."""
    with table.lock:
        summary = {"at_table": len(table.players), "chips": None, "wordle": None}
    if tg_id is None:
        return summary
    game = get_game(tg_id, today())
    summary["chips"] = _chips(tg_id)
    summary["wordle"] = {
        "finished": bool(game and game["finished"]), "solved": bool(game and game["solved"]),
        "tries": len(game["guesses"]) if game else 0, "max_tries": MAX_TRIES,
        "streak": _stats().get(tg_id, {}).get("streak", 0),
    }
    return summary


# ---------- тренировка ----------
def _practice_key() -> str:
    key = session.get("wordle_key")
    if not key:
        key = session["wordle_key"] = secrets.token_hex(12)
    return key


def _new_practice(key: str) -> dict:
    exclude = daily_word(today())
    game = {"word": random.choice([w for w in ANSWERS if w != exclude]), "guesses": [], "at": time.time()}
    with _practice_lock:
        now = time.time()
        for k in [k for k, g in _practice.items() if now - g["at"] > PRACTICE_TTL]:
            del _practice[k]
        _practice[key] = game
    return game


def _practice_state(game: dict) -> dict:
    finished = game["word"] in game["guesses"] or len(game["guesses"]) >= MAX_TRIES
    return {
        "mode": "practice", "max_tries": MAX_TRIES,
        "rows": [{"word": w, "marks": score(w, game["word"])} for w in game["guesses"]],
        "finished": finished, "solved": game["word"] in game["guesses"],
        "answer": game["word"] if finished else None,
    }


# ---------- маршруты ----------
@wordle_bp.route("/wordle")
def wordle_page():
    return render_template("wordle.html", user=session.get("user"), reward=REWARD)


@wordle_bp.route("/wordle/daily")
def daily():
    return jsonify(_daily_state(_tg_id()))


@wordle_bp.route("/wordle/daily/guess", methods=["POST"])
def daily_guess():
    tg_id = _tg_id()
    if tg_id is None:
        return _err("Войдите через Telegram, чтобы играть в слово дня", 401)
    day = today()
    if (request.get_json(silent=True) or {}).get("day") != day.isoformat():
        return _err("Наступил новый день — слово обновилось", 409)
    word, error = _read_guess()
    if error:
        return _err(error)
    game, error = add_guess(tg_id, day, word, daily_word(day), MAX_TRIES)
    if error:
        return _err(error, 409)
    state = _daily_state(tg_id)
    if game["just_solved"]:
        with table.lock:
            state["chips"] = table.give_chips(tg_id, REWARD)  # сидящему за столом — прямо в стек
            if table.player_of(tg_id):
                table.broadcast()
        state["won_chips"] = REWARD
    return jsonify(state)


@wordle_bp.route("/wordle/practice")
def practice():
    key = _practice_key()
    with _practice_lock:
        game = _practice.get(key)
    return jsonify(_practice_state(game or _new_practice(key)))


@wordle_bp.route("/wordle/practice/new", methods=["POST"])
def practice_new():
    return jsonify(_practice_state(_new_practice(_practice_key())))


@wordle_bp.route("/wordle/practice/guess", methods=["POST"])
def practice_guess():
    key = _practice_key()
    word, error = _read_guess()
    if error:
        return _err(error)
    with _practice_lock:
        game = _practice.get(key)
        if game is None:
            return _err("Тренировка устарела — начните новую", 409)
        if _practice_state(game)["finished"]:
            return _err("Слово уже отгадано — начните новое", 409)
        game["guesses"].append(word)
        game["at"] = time.time()
        return jsonify(_practice_state(game))


@wordle_bp.route("/wordle/today")
def today_results():
    """Как сегодня сыграли остальные. Буквы видны только тем, кто уже закончил свою партию — без спойлеров."""
    me = _tg_id()
    day = today()
    answer = daily_word(day)
    games = games_of_day(day)
    mine = next((g for g in games if g["tg_id"] == me), None)
    reveal = bool(mine and mine["finished"])
    info, loading = user_infos([g["tg_id"] for g in games])
    players = []
    for g in games:
        i = info.get(g["tg_id"], {})
        players.append({
            "tg_id": str(g["tg_id"]), "username": i.get("username", ""), "first_name": i.get("first_name", ""),
            "avatar": f"/poker/avatar/{g['tg_id']}",
            "rows": [{"word": w if reveal else None, "marks": score(w, answer)} for w in g["guesses"]],
            "finished": g["finished"], "solved": g["solved"],
        })
    return jsonify({"players": players, "reveal": reveal, "loading": loading, "me": str(me) if me else None,
                    "max_tries": MAX_TRIES, "number": (day - EPOCH).days + 1})


@wordle_bp.route("/wordle/leaderboard")
def leaderboard():
    me = _tg_id()
    stats = _stats()
    info, loading = user_infos(list(stats))
    users = []
    for tg_id, s in stats.items():
        i = info.get(tg_id, {})
        users.append({"tg_id": str(tg_id), "username": i.get("username", ""), "first_name": i.get("first_name", ""),
                      "avatar": f"/poker/avatar/{tg_id}", **s})
    users.sort(key=lambda u: (-u["streak"], -u["wins"], -u["max_streak"]))
    place = next((i + 1 for i, u in enumerate(users) if u["tg_id"] == str(me)), None)
    return jsonify({"users": users[:50], "total": len(users), "loading": loading,
                    "me": str(me) if me else None, "my_place": place})
