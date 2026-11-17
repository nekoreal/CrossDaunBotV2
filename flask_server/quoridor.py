import secrets
import threading
import time
from dataclasses import dataclass

from flask import Blueprint, render_template, session, redirect, url_for, request
from flask_socketio import emit, join_room

from flask_server.dashboard import socketio
from flask_server.quoridor_logic import CENTER, QuoridorGame, TURN_SECONDS


NS = "/quoridor"
LOBBY_ROOM = "quoridor_lobby"
PLAYER_COLORS = ("#00f2fe", "#ffb703", "#9d4edd", "#00e676")
quoridor_bp = Blueprint("quoridor_bp", __name__)


@dataclass
class WaitingPlayer:
    tg_id: int
    sid: str
    username: str
    photo_url: str


@dataclass
class ActiveGame:
    game_id: str
    game: QuoridorGame
    sids: dict[int, str]


_lock = threading.RLock()
_waiting: list[WaitingPlayer] = []
_games: dict[str, ActiveGame] = {}
_games_by_user: dict[int, str] = {}


def _session_user():
    user = session.get("user")
    if not isinstance(user, dict) or not user.get("id"):
        return None
    try:
        tg_id = int(user["id"])
    except (TypeError, ValueError):
        return None
    return {
        "tg_id": tg_id,
        "username": (user.get("username") or user.get("first_name") or f"Игрок {tg_id}"),
        "photo_url": user.get("photo_url") or "",
    }


def _lobby_state() -> dict:
    return {
        "waiting": [
            {"username": player.username, "photo_url": player.photo_url}
            for player in _waiting
        ],
        "needed": max(0, 4 - len(_waiting)),
    }


def _send_lobby_state() -> None:
    socketio.emit("lobby_state", _lobby_state(), room=LOBBY_ROOM, namespace=NS)


def _send_game_state(active: ActiveGame) -> None:
    game = active.game
    for index, pawn in enumerate(game.players):
        sid = active.sids.get(pawn.tg_id)
        if not sid:
            continue
        socketio.emit("game_state", {
            "players": [
                {
                    "username": player.username,
                    "photo_url": player.photo_url,
                    "row": player.row,
                    "col": player.col,
                    "walls": player.walls,
                    "active": player.active,
                    "surrendered": player.surrendered,
                    "auto_turns": player.auto_turns,
                    "reached_center": (
                        (player.row, player.col) == CENTER and not player.surrendered
                    ),
                    "place": player.place,
                    "color": PLAYER_COLORS[player_index],
                }
                for player_index, player in enumerate(game.players)
            ],
            "walls": [
                {"row": wall.row, "col": wall.col, "orientation": wall.orientation}
                for wall in game.walls
            ],
            "current_turn": game.current_turn,
            "my_index": index,
            "deadline": game.turn_deadline,
            "legal_moves": game.legal_moves(),
            "winner": game.winner,
            "finished": game.finished,
            "turn_seconds": TURN_SECONDS,
        }, to=sid, namespace=NS)


def _start_turn_timer(game_id: str, serial: int, deadline: float) -> None:
    socketio.sleep(max(0, deadline - time.time()))
    with _lock:
        active = _games.get(game_id)
        if (
            active is None
            or active.game.finished
            or active.game.turn_serial != serial
            or active.game.turn_deadline > time.time()
        ):
            return
        active.game.auto_move()
        _send_game_state(active)
        if active.game.finished:
            _retire_game(active)
        else:
            _schedule_timer(active)


def _schedule_timer(active: ActiveGame) -> None:
    socketio.start_background_task(
        _start_turn_timer,
        active.game_id,
        active.game.turn_serial,
        active.game.turn_deadline,
    )


def _retire_game(active: ActiveGame) -> None:
    _games.pop(active.game_id, None)
    for player in active.game.players:
        if _games_by_user.get(player.tg_id) == active.game_id:
            _games_by_user.pop(player.tg_id, None)


@quoridor_bp.route("/quoridor")
def quoridor_page():
    user = _session_user()
    if user is None:
        return redirect(url_for("entry_telegram_bp.home"))
    return render_template("quoridor.html")


@socketio.on("connect", namespace=NS)
def quoridor_connect(_auth=None):
    if _session_user() is None:
        return False
    join_room(LOBBY_ROOM)


@socketio.on("queue_join", namespace=NS)
def quoridor_queue_join(_data=None):
    user = _session_user()
    if user is None:
        emit("alert", {"message": "Сначала войдите через Telegram"})
        return

    with _lock:
        game_id = _games_by_user.get(user["tg_id"])
        if game_id and game_id in _games:
            active = _games[game_id]
            active.sids[user["tg_id"]] = request.sid
            _send_game_state(active)
            return

        _waiting[:] = [player for player in _waiting if player.tg_id != user["tg_id"]]
        _waiting.append(WaitingPlayer(
            tg_id=user["tg_id"],
            sid=request.sid,
            username=user["username"],
            photo_url=user["photo_url"],
        ))

        if len(_waiting) >= 4:
            players = _waiting[:4]
            del _waiting[:4]
            game = QuoridorGame([
                {"tg_id": player.tg_id, "username": player.username, "photo_url": player.photo_url}
                for player in players
            ])
            game_id = secrets.token_urlsafe(9)
            active = ActiveGame(
                game_id=game_id,
                game=game,
                sids={player.tg_id: player.sid for player in players},
            )
            _games[game_id] = active
            for player in players:
                _games_by_user[player.tg_id] = game_id
            _send_game_state(active)
            _schedule_timer(active)

        _send_lobby_state()


@socketio.on("queue_leave", namespace=NS)
def quoridor_queue_leave(_data=None):
    user = _session_user()
    if user is None:
        return
    with _lock:
        _waiting[:] = [
            player for player in _waiting
            if not (player.tg_id == user["tg_id"] and player.sid == request.sid)
        ]
        _send_lobby_state()


@socketio.on("move", namespace=NS)
def quoridor_move(data=None):
    user = _session_user()
    data = data if isinstance(data, dict) else {}
    if user is None:
        emit("alert", {"message": "Сначала войдите через Telegram"})
        return
    try:
        row, col = data.get("row"), data.get("col")
        if type(row) is not int or type(col) is not int:
            raise ValueError
    except (TypeError, ValueError):
        emit("alert", {"message": "Некорректная клетка"})
        return

    with _lock:
        game_id = _games_by_user.get(user["tg_id"])
        active = _games.get(game_id) if game_id else None
        index = next(
            (i for i, player in enumerate(active.game.players) if player.tg_id == user["tg_id"]),
            None,
        ) if active else None
        if active is None or index is None or active.sids.get(user["tg_id"]) != request.sid:
            emit("alert", {"message": "Вы сейчас не за игровым столом"})
            return
        if not active.game.move(index, row, col):
            emit("alert", {"message": "Так сходить нельзя"})
            return
        _send_game_state(active)
        if active.game.finished:
            _retire_game(active)
        else:
            _schedule_timer(active)


@socketio.on("place_wall", namespace=NS)
def quoridor_place_wall(data=None):
    user = _session_user()
    data = data if isinstance(data, dict) else {}
    if user is None:
        emit("alert", {"message": "Сначала войдите через Telegram"})
        return
    try:
        row, col = data.get("row"), data.get("col")
        if type(row) is not int or type(col) is not int:
            raise ValueError
    except (TypeError, ValueError):
        emit("alert", {"message": "Некорректное место для стены"})
        return
    orientation = data.get("orientation")

    with _lock:
        game_id = _games_by_user.get(user["tg_id"])
        active = _games.get(game_id) if game_id else None
        index = next(
            (i for i, player in enumerate(active.game.players) if player.tg_id == user["tg_id"]),
            None,
        ) if active else None
        if active is None or index is None or active.sids.get(user["tg_id"]) != request.sid:
            emit("alert", {"message": "Вы сейчас не за игровым столом"})
            return
        if not active.game.place_wall(index, row, col, orientation):
            emit("alert", {"message": "Стена здесь недопустима"})
            return
        _send_game_state(active)
        _schedule_timer(active)


@socketio.on("surrender", namespace=NS)
def quoridor_surrender(_data=None):
    user = _session_user()
    if user is None:
        emit("alert", {"message": "Сначала войдите через Telegram"})
        return

    with _lock:
        game_id = _games_by_user.get(user["tg_id"])
        active = _games.get(game_id) if game_id else None
        index = next(
            (i for i, player in enumerate(active.game.players) if player.tg_id == user["tg_id"]),
            None,
        ) if active else None
        if active is None or index is None or active.sids.get(user["tg_id"]) != request.sid:
            emit("alert", {"message": "Вы сейчас не за игровым столом"})
            return
        serial = active.game.turn_serial
        if not active.game.surrender(index):
            emit("alert", {"message": "Нельзя сдаться в завершённой партии"})
            return
        _send_game_state(active)
        if active.game.finished:
            _retire_game(active)
        elif serial != active.game.turn_serial:
            _schedule_timer(active)


@socketio.on("disconnect", namespace=NS)
def quoridor_disconnect(*_args):
    with _lock:
        removed = False
        for index, player in enumerate(_waiting):
            if player.sid == request.sid:
                _waiting.pop(index)
                removed = True
                break
        if removed:
            _send_lobby_state()
