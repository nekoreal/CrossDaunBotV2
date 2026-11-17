import secrets
import threading
import time
from dataclasses import dataclass, field

from flask import Blueprint, render_template, session, redirect, url_for, request
from flask_socketio import emit, join_room

from flask_server.dashboard import socketio
from flask_server.quoridor_logic import CENTER, QuoridorGame, TURN_SECONDS


NS = "/quoridor"
LOBBY_ROOM = "quoridor_lobby"
PLAYER_COLORS = ("#00f2fe", "#ffb703", "#9d4edd", "#00e676")
RECONNECT_GRACE_SECONDS = 30
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
    reconnect_deadlines: dict[int, float] = field(default_factory=dict)
    reconnect_tokens: dict[int, int] = field(default_factory=dict)
    paused_turn_seconds: dict[int, float] = field(default_factory=dict)


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
                    "reconnect_deadline": active.reconnect_deadlines.get(player.tg_id),
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
            active is not None
            and not active.game.finished
            and active.game.turn_serial == serial
            and active.game.turn_deadline <= time.time()
        ):
            current_id = active.game.players[active.game.current_turn].tg_id
            reconnect_deadline = active.reconnect_deadlines.get(current_id)
            if reconnect_deadline is not None:
                active.paused_turn_seconds[current_id] = 0
                active.game.turn_serial += 1
                active.game.turn_deadline = reconnect_deadline
                _send_game_state(active)
                return
        if (
            active is None
            or active.game.finished
            or active.game.turn_serial != serial
            or active.game.turn_deadline > time.time()
            or active.game.players[active.game.current_turn].tg_id in active.reconnect_deadlines
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


def _start_reconnect_timer(
    game_id: str,
    tg_id: int,
    token: int,
    deadline: float,
) -> None:
    socketio.sleep(max(0, deadline - time.time()))
    _expire_reconnect(game_id, tg_id, token, deadline)


def _expire_reconnect(
    game_id: str,
    tg_id: int,
    token: int,
    deadline: float,
    now: float | None = None,
) -> bool:
    current_time = time.time() if now is None else now
    with _lock:
        active = _games.get(game_id)
        if (
            active is None
            or active.reconnect_tokens.get(tg_id) != token
            or active.reconnect_deadlines.get(tg_id) != deadline
            or deadline > current_time
        ):
            return False

        index = next(
            (i for i, player in enumerate(active.game.players) if player.tg_id == tg_id),
            None,
        )
        if index is None:
            return False

        was_current_turn = active.game.current_turn == index
        if not active.game.surrender(index):
            return False
        active.reconnect_deadlines.pop(tg_id, None)
        active.paused_turn_seconds.pop(tg_id, None)
        _send_game_state(active)
        if active.game.finished:
            _retire_game(active)
        elif was_current_turn:
            _schedule_timer(active)
        return True


def _schedule_reconnect_timer(
    active: ActiveGame,
    tg_id: int,
    token: int,
    deadline: float,
) -> None:
    socketio.start_background_task(
        _start_reconnect_timer,
        active.game_id,
        tg_id,
        token,
        deadline,
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
            index = next(
                (i for i, player in enumerate(active.game.players) if player.tg_id == user["tg_id"]),
                None,
            )
            deadline = active.reconnect_deadlines.get(user["tg_id"])
            if deadline is not None and deadline <= time.time():
                active.sids[user["tg_id"]] = request.sid
                _expire_reconnect(
                    game_id,
                    user["tg_id"],
                    active.reconnect_tokens[user["tg_id"]],
                    deadline,
                )
                emit("alert", {"message": "Время на переподключение истекло, вы сдались"})
                return
            previous_sid = active.sids.get(user["tg_id"])
            if previous_sid != request.sid and index is not None:
                was_disconnected = user["tg_id"] in active.reconnect_deadlines
                active.reconnect_deadlines.pop(user["tg_id"], None)
                active.reconnect_tokens[user["tg_id"]] = active.reconnect_tokens.get(user["tg_id"], 0) + 1
                active.sids[user["tg_id"]] = request.sid
                if was_disconnected and active.game.current_turn == index:
                    remaining = active.paused_turn_seconds.pop(user["tg_id"], TURN_SECONDS)
                    active.game.turn_serial += 1
                    active.game.turn_deadline = time.time() + remaining
                    _schedule_timer(active)
                else:
                    active.paused_turn_seconds.pop(user["tg_id"], None)
            else:
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


@socketio.on("preview_wall", namespace=NS)
def quoridor_preview_wall(data=None):
    user = _session_user()
    data = data if isinstance(data, dict) else {}
    if user is None:
        emit("wall_preview_result", {"valid": False, "seq": data.get("seq")})
        return
    row, col, orientation, seq = (
        data.get("row"),
        data.get("col"),
        data.get("orientation"),
        data.get("seq"),
    )
    if (
        type(row) is not int
        or type(col) is not int
        or type(seq) is not int
        or orientation not in ("horizontal", "vertical")
    ):
        emit("wall_preview_result", {"valid": False, "seq": seq})
        return

    with _lock:
        game_id = _games_by_user.get(user["tg_id"])
        active = _games.get(game_id) if game_id else None
        index = next(
            (i for i, player in enumerate(active.game.players) if player.tg_id == user["tg_id"]),
            None,
        ) if active else None
        valid = bool(
            active
            and index is not None
            and active.sids.get(user["tg_id"]) == request.sid
            and active.game.can_place_wall(index, row, col, orientation)
        )
        emit("wall_preview_result", {"valid": valid, "seq": seq})


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
        for index, player in enumerate(_waiting):
            if player.sid == request.sid:
                _waiting.pop(index)
                _send_lobby_state()
                return

        for active in _games.values():
            tg_id = next(
                (player_id for player_id, sid in active.sids.items() if sid == request.sid),
                None,
            )
            if tg_id is None:
                continue
            player_index = next(
                (i for i, player in enumerate(active.game.players) if player.tg_id == tg_id),
                None,
            )
            if player_index is None or not active.game.players[player_index].active:
                return

            now = time.time()
            deadline = now + RECONNECT_GRACE_SECONDS
            active.reconnect_tokens[tg_id] = active.reconnect_tokens.get(tg_id, 0) + 1
            token = active.reconnect_tokens[tg_id]
            active.reconnect_deadlines[tg_id] = deadline
            if active.game.current_turn == player_index:
                active.paused_turn_seconds[tg_id] = max(
                    0,
                    active.game.turn_deadline - now,
                )
                active.game.turn_serial += 1
                active.game.turn_deadline = deadline

            _send_game_state(active)
            _schedule_reconnect_timer(active, tg_id, token, deadline)
            return
