import time
import random
from collections import deque
from dataclasses import dataclass, field
from itertools import combinations
from threading import RLock
from flask import Blueprint, request, session, render_template
from flask_socketio import emit

from telegram_bot.tg_db.db_controllers.poker_controller import (
    get_poker_profile,
    set_chips_many,
    set_card_style,
    claim_bonus,
)
from flask_server.dashboard import socketio

NS = "/poker"
MAX_SEATS = 10
SB, BB = 10, 20
TURN_TIME = 25          # сек на ход
RUNOUT_DELAY = 1.3      # пауза между улицами, когда все в олл-ине
DISCONNECT_GRACE = 20   # сек, через сколько отключившегося игрока поднимают из-за стола
MAX_TIMEOUTS = 2        # столько автоходов подряд — и игрок встаёт из-за стола
BONUS_AMOUNT = 500
BONUS_COOLDOWN = 12 * 3600
CARD_STYLES = {"classic", "four", "neon", "gold"}

# --- оценка комбинаций (та же схема, что и в клиенте) ---
RANKS = "23456789TJQKA"
HAND_NAMES = ["Старшая карта", "Пара", "Две пары", "Сет", "Стрит", "Флеш", "Фулл-хаус", "Каре", "Стрит-флеш"]
KB = 15 ** 5


def score5(cards) -> int:
    r = sorted((RANKS.index(c[0]) + 2 for c in cards), reverse=True)
    flush = all(c[1] == cards[0][1] for c in cards)
    cnt = {}
    for v in r:
        cnt[v] = cnt.get(v, 0) + 1
    groups = sorted(((n, v) for v, n in cnt.items()), reverse=True)
    straight = r[0] if (r[0] - r[4] == 4 and len(groups) == 5) else (5 if r == [14, 5, 4, 3, 2] else 0)
    if straight and flush:
        cat = 8
    elif groups[0][0] == 4:
        cat = 7
    elif groups[0][0] == 3 and groups[1][0] == 2:
        cat = 6
    elif flush:
        cat = 5
    elif straight:
        cat = 4
    elif groups[0][0] == 3:
        cat = 3
    elif groups[0][0] == 2 and groups[1][0] == 2:
        cat = 2
    elif groups[0][0] == 2:
        cat = 1
    else:
        cat = 0
    kickers = [straight] if cat in (4, 8) else [v for _, v in groups]
    k = 0
    for v in kickers:
        k = k * 15 + v
    return cat * KB + k


def best_score(cards) -> int:
    return max(score5(c) for c in combinations(cards, 5))


def hand_name(score: int) -> str:
    cat = score // KB
    return "Роял-флеш" if cat == 8 and score % KB == 14 else HAND_NAMES[cat]


@dataclass
class Player:
    tg_id: int
    name: str
    photo_url: str
    seat: int
    stack: int
    cards: list = field(default_factory=list)
    bet: int = 0
    total: int = 0          # всего вложено в банк за раздачу
    folded: bool = False
    all_in: bool = False
    acted: bool = False
    in_hand: bool = False
    last: str = ""
    timeouts: int = 0
    score: int = 0


class Table:
    def __init__(self):
        self.lock = RLock()
        self.seats: list[Player | None] = [None] * MAX_SEATS
        self.hand: list[Player] = []        # участники текущей раздачи в порядке мест
        self.sids: dict[str, int | None] = {}
        self.profiles: dict[int, dict] = {}  # tg_id -> {bonus_at, card_style}
        self.history = deque(maxlen=15)
        self.status = "waiting"              # waiting, betting, showdown
        self.stage = ""
        self.hand_no = 0
        self.dealer_seat = -1
        self.deck: list[str] = []
        self.board: list[str] = []
        self.cur = 0                         # индекс в self.hand
        self.cur_bet = 0
        self.min_raise = BB
        self.deadline = None
        self.winners: list[dict] = []
        self.gen = 0                         # поколение таймера: старые таймеры игнорируются

    # ---------- служебное ----------
    def seat_of(self, tg_id) -> Player | None:
        return next((p for p in self.seats if p and p.tg_id == tg_id), None)

    def live(self):
        return [p for p in self.hand if not p.folded]

    def pot(self) -> int:
        return sum(p.total for p in self.hand)

    def online_ids(self) -> set:
        return {t for t in self.sids.values() if t is not None}

    def save_chips(self, players):
        try:
            set_chips_many({p.tg_id: p.stack for p in players})
        except Exception as e:
            print(f"Покер: не удалось сохранить фишки: {e}")

    def remove(self, p: Player):
        self.seats[p.seat] = None
        self.save_chips([p])

    def cleanup(self, remove_busted: bool) -> bool:
        """Поднимает из-за стола отключившихся, AFK и (опционально) игроков без фишек."""
        online = self.online_ids()
        removed = False
        for p in [p for p in self.seats if p]:
            if p.tg_id not in online or p.timeouts >= MAX_TIMEOUTS or (remove_busted and p.stack <= 0):
                self.remove(p)
                removed = True
        return removed

    # ---------- подключения ----------
    def connect(self, sid, tg_id):
        self.sids[sid] = tg_id
        if tg_id is not None and tg_id not in self.profiles:
            profile = get_poker_profile(tg_id)
            if profile:
                self.profiles[tg_id] = profile

    def disconnect(self, sid) -> int | None:
        return self.sids.pop(sid, None)

    # ---------- места ----------
    def sit(self, user: dict, seat: int) -> str | None:
        tg_id = int(user["id"])
        if not (0 <= seat < MAX_SEATS):
            return "Нет такого места"
        if self.seat_of(tg_id):
            return "Вы уже за столом"
        if self.seats[seat]:
            return "Место занято"
        profile = get_poker_profile(tg_id)
        if not profile:
            return "Пользователь не найден"
        self.profiles[tg_id] = profile
        if profile["chips"] <= 0:
            return "Нет фишек — заберите бонус"
        self.seats[seat] = Player(
            tg_id=tg_id,
            name=user.get("username") or f"id{tg_id}",
            photo_url=user.get("photo_url") or "",
            seat=seat,
            stack=profile["chips"],
        )
        return None

    def stand(self, tg_id) -> str | None:
        p = self.seat_of(tg_id)
        if not p:
            return "Вы не за столом"
        self.remove(p)
        # встал посреди раздачи = фолд; вложенные фишки остаются в банке
        if self.status == "betting" and p.in_hand and not p.folded:
            p.folded = True
            p.last = "Встал"
            if self.hand[self.cur] is p:
                self.next()
            elif len(self.live()) == 1:
                self.finish()
        return None

    # ---------- раздача ----------
    def start_hand(self, tg_id) -> str | None:
        if self.status == "betting":
            return "Раздача уже идёт"
        if not self.seat_of(tg_id):
            return "Сядьте за стол, чтобы раздать карты"
        self.cleanup(remove_busted=True)
        players = [p for p in self.seats if p]
        if len(players) < 2:
            return "Нужно минимум 2 игрока"

        self.hand_no += 1
        self.status, self.stage = "betting", "preflop"
        self.board, self.winners, self.deadline = [], [], None
        self.deck = [r + s for s in "shdc" for r in RANKS]
        random.shuffle(self.deck)
        for p in [p for p in self.seats if p]:
            p.in_hand = False
            p.cards = []
        for p in players:
            p.cards = [self.deck.pop(), self.deck.pop()]
            p.bet = p.total = 0
            p.folded = p.all_in = p.acted = False
            p.in_hand = True
            p.last = ""
        self.hand = players

        # дилер — следующее занятое место после прошлого дилера
        n = len(players)
        di = next((i for i, p in enumerate(players) if p.seat > self.dealer_seat), 0)
        self.dealer_seat = players[di].seat
        if n == 2:  # хедз-ап: дилер ставит малый блайнд и ходит первым на префлопе
            sb, bb = di, (di + 1) % n
        else:
            sb, bb = (di + 1) % n, (di + 2) % n
        self.post(players[sb], SB)
        self.post(players[bb], BB)
        self.cur_bet, self.min_raise = BB, BB
        self.cur = bb
        self.next()
        return None

    def post(self, p: Player, amount: int):
        amount = min(amount, p.stack)
        p.stack -= amount
        p.bet += amount
        p.total += amount
        if p.stack == 0:
            p.all_in = True

    def action(self, tg_id, kind: str, amount=None, auto=False) -> str | None:
        if self.status != "betting":
            return "Сейчас нет раздачи"
        p = self.hand[self.cur]
        if p.tg_id != tg_id or self.seat_of(tg_id) is not p:
            return "Сейчас не ваш ход"
        to_call = self.cur_bet - p.bet
        if kind == "call" and to_call == 0:
            kind = "check"
        if kind == "fold":
            p.folded = True
            p.last = "Фолд"
        elif kind == "check":
            if to_call:
                return "Нельзя чекнуть — нужно уравнять"
            p.last = "Чек"
        elif kind == "call":
            self.post(p, to_call)
            p.last = "Олл-ин" if p.all_in else "Колл"
        elif kind == "raise":
            try:
                to = int(amount)
            except (TypeError, ValueError):
                return "Неверная сумма"
            max_to = p.stack + p.bet
            to = min(to, max_to)
            if to <= self.cur_bet:
                return self.action(tg_id, "call")
            if to < self.cur_bet + self.min_raise and to < max_to:
                return "Слишком маленький рейз"
            self.post(p, to - p.bet)
            self.min_raise = max(self.min_raise, to - self.cur_bet)
            self.cur_bet = to
            for o in self.hand:
                if o is not p:
                    o.acted = False
            p.last = "Олл-ин" if p.all_in else f"Рейз {to}"
        else:
            return "Неизвестное действие"
        p.acted = True
        p.timeouts = p.timeouts + 1 if auto else 0
        self.next()
        return None

    def next(self):
        live = self.live()
        if len(live) == 1:
            return self.finish()
        need = [p for p in live if not p.all_in]
        if all(p.bet == self.cur_bet and (p.acted or len(need) < 2) for p in need):
            return self.next_stage()
        n = len(self.hand)
        self.cur = (self.cur + 1) % n
        while self.hand[self.cur].folded or self.hand[self.cur].all_in:
            self.cur = (self.cur + 1) % n
        self.push()

    def next_stage(self):
        for p in self.hand:
            p.bet = 0
            p.acted = False
        self.cur_bet, self.min_raise = 0, BB
        if self.stage == "river":
            return self.finish()
        count = 3 if self.stage == "preflop" else 1
        self.stage = {"preflop": "flop", "flop": "turn", "turn": "river"}[self.stage]
        for _ in range(count):
            self.board.append(self.deck.pop())
        if len([p for p in self.live() if not p.all_in]) < 2:
            # торговаться больше некому — докладываем улицы с паузой
            self.gen += 1
            self.deadline = None
            self.broadcast()
            socketio.start_background_task(self._delayed, self.gen, RUNOUT_DELAY, self.next_stage)
            return
        # первым ходит первый живой игрок после дилера
        n = len(self.hand)
        di = next(i for i, p in enumerate(self.hand) if p.seat == self.dealer_seat)
        self.cur = (di + 1) % n
        while self.hand[self.cur].folded or self.hand[self.cur].all_in:
            self.cur = (self.cur + 1) % n
        self.push()

    def finish(self):
        self.gen += 1
        self.status, self.deadline = "showdown", None
        live, total = self.live(), self.pot()
        res: list[dict] = []

        def give(p: Player, amount: int, hname: str):
            p.stack += amount
            r = next((x for x in res if x["id"] == str(p.tg_id)), None)
            if r:
                r["amount"] += amount
            else:
                res.append({"id": str(p.tg_id), "name": p.name, "amount": amount, "hand_name": hname})

        if len(live) == 1:
            give(live[0], total, "Все сфолдили")
        else:
            for p in live:
                p.score = best_score(p.cards + self.board)
            # сайд-поты: уровни по вкладам оставшихся в игре
            levels = sorted({p.total for p in live})
            prev = 0
            for i, level in enumerate(levels):
                hi = float("inf") if i == len(levels) - 1 else level
                amount = sum(max(0, min(p.total, hi) - prev) for p in self.hand)
                eligible = [p for p in live if p.total >= level]
                top = max(p.score for p in eligible)
                ws = [p for p in eligible if p.score == top]
                share, rest = divmod(amount, len(ws))
                for j, w in enumerate(ws):
                    give(w, share + (1 if j < rest else 0), hand_name(w.score))
                prev = level

        self.winners = [r for r in res if r["amount"] > 0]
        for p in self.hand:
            p.bet = 0
        self.save_chips([p for p in self.seats if p])
        result = {"hand_no": self.hand_no, "pot": total, "winners": self.winners}
        self.history.append(result)
        socketio.emit("hand_result", result, namespace=NS)
        self.broadcast()

    # ---------- таймеры ----------
    def push(self):
        self.schedule()
        self.broadcast()

    def schedule(self):
        self.gen += 1
        self.deadline = None
        if self.status != "betting":
            return
        self.deadline = time.time() + TURN_TIME
        socketio.start_background_task(self._delayed, self.gen, TURN_TIME, self._on_timeout)

    def _on_timeout(self):
        p = self.hand[self.cur]
        self.action(p.tg_id, "fold" if self.cur_bet - p.bet else "check", auto=True)

    def _delayed(self, gen, delay, fn):
        socketio.sleep(delay)
        with self.lock:
            if self.gen == gen and self.status == "betting":
                fn()

    # ---------- бонус и настройки ----------
    def claim_bonus(self, tg_id) -> tuple[str | None, int]:
        p = self.seat_of(tg_id)
        if p and self.status == "betting" and p.in_hand and not p.folded:
            return "Забрать бонус можно между раздачами", 0
        result = claim_bonus(tg_id, BONUS_AMOUNT, BONUS_COOLDOWN, time.time(), add_to_chips=p is None)
        if result is None:
            return "Бонус ещё недоступен", 0
        self.profiles.setdefault(tg_id, {})["bonus_at"] = result["bonus_at"]
        if p:
            p.stack += BONUS_AMOUNT
            self.save_chips([p])
        else:
            self.profiles[tg_id]["chips"] = result["chips"]
        return None, BONUS_AMOUNT

    def save_settings(self, tg_id, card_style) -> str | None:
        if card_style not in CARD_STYLES:
            return "Неизвестный стиль карт"
        set_card_style(tg_id, card_style)
        self.profiles.setdefault(tg_id, {})["card_style"] = card_style
        return None

    # ---------- состояние ----------
    def view(self, tg_id) -> dict:
        me = self.seat_of(tg_id) if tg_id is not None else None
        live_count = len(self.live())
        profile = self.profiles.get(tg_id, {}) if tg_id is not None else {}
        players = []
        for p in self.seats:
            if not p:
                continue
            show = p.in_hand and p.cards and (
                p is me or (self.status == "showdown" and live_count > 1 and not p.folded))
            players.append({
                "id": str(p.tg_id), "seat": p.seat, "name": p.name, "photo_url": p.photo_url,
                "stack": p.stack, "bet": p.bet if p.in_hand else 0, "folded": p.folded and p.in_hand,
                "all_in": p.all_in and p.in_hand, "in_hand": p.in_hand and self.status != "waiting",
                "last_action": p.last if p.in_hand else "", "is_dealer": p.seat == self.dealer_seat and self.status != "waiting",
                "cards": p.cards if show else None,
            })
        to_act = str(self.hand[self.cur].tg_id) if self.status == "betting" and self.deadline else None
        return {
            "status": self.status, "stage": self.stage if self.status == "betting" else "",
            "hand_no": self.hand_no, "blinds": [SB, BB], "pot": self.pot() if self.status != "waiting" else 0,
            "community": self.board, "current_bet": self.cur_bet, "min_raise_to": self.cur_bet + self.min_raise,
            "to_act": to_act, "deadline": self.deadline, "winners": self.winners,
            "players": players, "max_seats": MAX_SEATS,
            "me": str(me.tg_id) if me else None,
            "logged_in": tg_id is not None,
            "bank_chips": profile.get("chips"),
            "bonus_next_at": profile.get("bonus_at", 0), "bonus_amount": BONUS_AMOUNT,
            "card_style": profile.get("card_style"),
        }

    def send_state(self, sid):
        socketio.emit("table_state", self.view(self.sids.get(sid)), to=sid, namespace=NS)

    def broadcast(self):
        for sid in list(self.sids):
            self.send_state(sid)


table = Table()
poker_bp = Blueprint("poker_bp", __name__)


@poker_bp.route("/poker")
def poker_page():
    user = session.get("user")
    card_style = None
    if user:
        profile = get_poker_profile(int(user["id"]))
        card_style = profile and profile["card_style"]
    return render_template("poker.html", user=user, card_style=card_style)


def _tg_id():
    user = session.get("user")
    return int(user["id"]) if user else None


def _alert(message):
    emit("alert", {"message": message})


def _disconnect_cleanup():
    socketio.sleep(DISCONNECT_GRACE)
    with table.lock:
        if table.status != "betting" and table.cleanup(remove_busted=False):
            table.broadcast()


@socketio.on("connect", namespace=NS)
def poker_connect(auth=None):
    with table.lock:
        table.connect(request.sid, _tg_id())


@socketio.on("disconnect", namespace=NS)
def poker_disconnect(*args):
    with table.lock:
        tg_id = table.disconnect(request.sid)
        seated = tg_id is not None and table.seat_of(tg_id) is not None
    if seated:
        socketio.start_background_task(_disconnect_cleanup)


@socketio.on("join_table", namespace=NS)
def poker_join(data=None):
    with table.lock:
        table.send_state(request.sid)
        for result in table.history:
            emit("hand_result", result)


@socketio.on("sit", namespace=NS)
def poker_sit(data=None):
    user = session.get("user")
    if not user:
        return _alert("Войдите через Telegram, чтобы сесть за стол")
    try:
        seat = int((data or {}).get("seat"))
    except (TypeError, ValueError):
        return _alert("Нет такого места")
    with table.lock:
        error = table.sit(user, seat)
        if error:
            return _alert(error)
        table.broadcast()


@socketio.on("stand", namespace=NS)
def poker_stand(data=None):
    tg_id = _tg_id()
    if tg_id is None:
        return
    with table.lock:
        error = table.stand(tg_id)
        if error:
            return _alert(error)
        table.profiles.pop(tg_id, None)
        table.connect(request.sid, tg_id)  # перечитать баланс из БД
        table.broadcast()


@socketio.on("start_hand", namespace=NS)
def poker_start_hand(data=None):
    tg_id = _tg_id()
    if tg_id is None:
        return _alert("Войдите через Telegram")
    with table.lock:
        error = table.start_hand(tg_id)
        if error:
            table.broadcast()
            return _alert(error)


@socketio.on("player_action", namespace=NS)
def poker_action(data=None):
    tg_id = _tg_id()
    data = data or {}
    if tg_id is None:
        return _alert("Войдите через Telegram")
    with table.lock:
        error = table.action(tg_id, data.get("type"), data.get("amount"))
        if error:
            return _alert(error)


@socketio.on("claim_bonus", namespace=NS)
def poker_claim_bonus(data=None):
    tg_id = _tg_id()
    if tg_id is None:
        return _alert("Войдите через Telegram")
    with table.lock:
        error, amount = table.claim_bonus(tg_id)
        if error:
            return _alert(error)
        emit("bonus_result", {"amount": amount, "message": f"💰 +{amount} фишек"})
        table.broadcast()


@socketio.on("save_settings", namespace=NS)
def poker_save_settings(data=None):
    tg_id = _tg_id()
    if tg_id is None:
        return  # гость: стиль хранится только в localStorage
    with table.lock:
        error = table.save_settings(tg_id, (data or {}).get("card_style"))
        if error:
            _alert(error)
