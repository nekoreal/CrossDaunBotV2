import time
import random
from collections import deque
from dataclasses import dataclass, field
from itertools import combinations
from threading import RLock
from flask import Blueprint, request, session, render_template
from flask_socketio import emit

from config import ADMIN_ID, POKER_MODER_ID
from telegram_bot.tg_db.db_controllers.poker_controller import (
    get_poker_profile,
    set_chips_many,
    add_chips,
    set_skin_choice,
    claim_bonus,
    get_all_skins,
    get_owned_skin_ids,
    buy_skin,
    get_settings,
    save_settings,
    create_skin,
    random_gallery_photo_ids,
)
from flask_server.dashboard import socketio

NS = "/poker"
MAX_PLAYERS_LIMIT = 10
RUNOUT_DELAY = 1.3      # пауза между улицами, когда все в олл-ине
DISCONNECT_GRACE = 25   # сек на переподключение, потом игрока убирают из-за стола
MAX_TIMEOUTS = 2        # столько автоходов подряд — и игрок убирается из-за стола
STD_SKINS = {"classic": "Классика", "four": "4 цвета", "neon": "Неон", "gold": "Золото"}
GALLERY_BACK_NAME = "🎲 Случайное фото из галереи"
GALLERY_BACK_PRICE = 5000
ADMIN_IDS = {ADMIN_ID, POKER_MODER_ID}  # модер голосования к покеру доступа не имеет

# настройки из админ-панели: ключ -> (по умолчанию, мин, макс, подпись)
SETTINGS_SPEC = {
    "small_blind": (10, 1, 1_000_000, "Малый блайнд"),
    "big_blind": (20, 2, 2_000_000, "Большой блайнд"),
    "turn_time": (35, 10, 180, "Время на ход, сек"),
    "showdown_time": (15, 3, 120, "Пауза до следующей раздачи, сек"),
    "max_players": (10, 2, MAX_PLAYERS_LIMIT, "Максимум игроков"),
    "bonus_amount": (500, 0, 10_000_000, "Бонус, фишек"),
    "bonus_cooldown_hours": (12, 1, 24 * 14, "Откат бонуса, часов"),
    "custom_back_price": (2000, 0, 100_000_000, "Цена загрузки своего задника"),
}
# эти настройки — цены магазина: меняются сразу (не ждут следующей раздачи) и живут во вкладке «Скины»
IMMEDIATE_SETTINGS = {"custom_back_price"}


def is_admin(tg_id) -> bool:
    return tg_id is not None and int(tg_id) in ADMIN_IDS


def validate_settings(values: dict) -> tuple[dict, str | None]:
    clean = {}
    for key, raw in (values or {}).items():
        if key not in SETTINGS_SPEC:
            continue
        _, lo, hi, label = SETTINGS_SPEC[key]
        try:
            v = int(raw)
        except (TypeError, ValueError):
            return {}, f"{label}: нужно целое число"
        if not lo <= v <= hi:
            return {}, f"{label}: от {lo} до {hi}"
        clean[key] = v
    return clean, None

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
    stack: int
    back_skin: str = "classic"
    front_skin: str = "classic"        # лицо его карт на руках (видно всем на шоудауне)
    gallery_photo: int | None = None   # задник «случайное фото»: фото на текущую раздачу
    ready: bool = False
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
        self.players: list[Player] = []      # за столом, в порядке посадки
        self.hand: list[Player] = []         # участники текущей раздачи
        self.sids: dict[str, int | None] = {}
        self.profiles: dict[int, dict] = {}  # tg_id -> {chips, bonus_at, front_skin, back_skin}
        self.history = deque(maxlen=15)
        self.running = False                 # все нажали «Готов» — раздачи идут одна за другой
        self.status = "waiting"              # waiting, betting, showdown
        self.stage = ""
        self.hand_no = 0
        self.dealer_idx = -1                 # индекс дилера в self.hand
        self.deck: list[str] = []
        self.board: list[str] = []
        self.cur = 0                         # индекс в self.hand
        self.cur_bet = 0
        self.min_raise = 0
        self._cfg: dict | None = None
        self.pending_cfg: dict | None = None   # изменения из админки ждут следующей раздачи
        self._skins: dict[int, dict] | None = None
        self.table_front = "classic"          # лицо карт на столе — по настройке дилера раздачи
        self.deadline = None
        self.next_hand_at = None
        self.winners: list[dict] = []
        self.gen = 0                         # поколение таймера: старые таймеры игнорируются
        self.offline_since: dict[int, float] = {}  # tg_id игрока за столом -> когда отключился

    # ---------- настройки ----------
    @property
    def cfg(self) -> dict:
        if self._cfg is None:
            self._cfg = {k: v[0] for k, v in SETTINGS_SPEC.items()}
            try:
                self._cfg.update({k: v for k, v in get_settings().items() if k in SETTINGS_SPEC})
            except Exception as e:
                print(f"Покер: не удалось загрузить настройки: {e}")
        return self._cfg

    def update_settings(self, values: dict) -> str | None:
        clean, error = validate_settings(values)
        if error:
            return error
        merged = {**self.cfg, **(self.pending_cfg or {}), **clean}
        if merged["big_blind"] < merged["small_blind"]:
            return "Большой блайнд не может быть меньше малого"
        save_settings(clean)
        if not self.running and self.status == "waiting":
            self._cfg = merged       # игры нет — применяем сразу
            self.pending_cfg = None
        else:
            for k in IMMEDIATE_SETTINGS & clean.keys():
                self.cfg[k] = clean[k]
            if any(merged[k] != self.cfg[k] for k in merged):
                self.pending_cfg = merged
        return None

    # ---------- скины ----------
    @property
    def skins(self) -> dict[int, dict]:
        if self._skins is None:
            try:
                skins = {sk["id"]: sk for sk in get_all_skins()}
                if not any(sk["data"].get("special") == "gallery" for sk in skins.values()):
                    # системный задник: каждую раздачу — случайное фото из галереи
                    sk = create_skin("back", GALLERY_BACK_NAME, GALLERY_BACK_PRICE, {"special": "gallery"})
                    skins[sk["id"]] = sk
                self._skins = skins
            except Exception as e:
                print(f"Покер: не удалось загрузить скины: {e}")
                return {}
        return self._skins

    def is_gallery_back(self, key) -> bool:
        try:
            sk = self.skins.get(int(key))
        except (TypeError, ValueError):
            return False
        return bool(sk) and sk["data"].get("special") == "gallery"

    def reload_skins(self):
        self._skins = None

    def skin_desc(self, key, kind: str) -> dict:
        """Описание скина для клиента: стандартный — только ключ, свой — картинки и цвета."""
        key = str(key or "classic")
        if key in STD_SKINS:
            return {"key": key}
        try:
            sk = self.skins.get(int(key))
        except ValueError:
            sk = None
        if not sk or sk["kind"] != kind:
            return {"key": "classic"}
        url = lambda part, s3_key: f"/poker/skin_img/{sk['id']}/{part}?v={s3_key.split('/')[0][:10]}"
        data = sk["data"]
        if kind == "back":
            if data.get("special") == "gallery":
                return {"key": key, "special": "gallery"}
            return {"key": key, "image": url("back", data["image"])}
        return {"key": key, "bg": data.get("bg"), "colors": data.get("colors", {}),
                "images": {r: url(r, k) for r, k in data.get("images", {}).items()}}

    def back_desc(self, p: Player) -> dict:
        desc = self.skin_desc(p.back_skin, "back")
        if desc.get("special") == "gallery" and p.gallery_photo:
            desc = {**desc, "image": f"/poker/gallery_photo/{p.gallery_photo}?card=1"}
        return desc

    def can_use_skin(self, tg_id, kind: str, key: str) -> bool:
        if key in STD_SKINS:
            return True
        try:
            sk = self.skins.get(int(key))
        except ValueError:
            return False
        if not sk or sk["kind"] != kind:
            return False
        if sk["owner_tg_id"] is None and sk["price"] == 0 and sk["is_active"]:
            return True
        return sk["id"] in get_owned_skin_ids(tg_id)

    def select_skin(self, tg_id, kind: str, key: str) -> str | None:
        if kind not in ("front", "back"):
            return "Неизвестный тип скина"
        key = str(key)
        if not self.can_use_skin(tg_id, kind, key):
            return "Этот скин вам недоступен"
        set_skin_choice(tg_id, kind, key)
        self.profiles.setdefault(tg_id, {})[f"{kind}_skin"] = key
        p = self.player_of(tg_id)
        if p:
            setattr(p, f"{kind}_skin", key)
        return None

    def charge(self, tg_id, amount: int) -> str | None:
        """Списывает фишки: со стека, если игрок за столом (и не в активной раздаче), иначе — в БД."""
        if amount <= 0:
            return None
        p = self.player_of(tg_id)
        if p:
            if self.status == "betting" and p.in_hand and not p.folded:
                return "Покупки — между раздачами (или после фолда)"
            if p.stack < amount:
                return "Недостаточно фишек"
            p.stack -= amount
            self.save_chips([p])
            return None
        profile = get_poker_profile(tg_id)
        if not profile or profile["chips"] < amount:
            return "Недостаточно фишек"
        new = add_chips(tg_id, -amount)
        self.profiles.setdefault(tg_id, {})["chips"] = new
        return None

    def refund(self, tg_id, amount: int):
        self.give_chips(tg_id, amount)

    def give_chips(self, tg_id, amount: int) -> int | None:
        p = self.player_of(tg_id)
        if p:
            p.stack = max(0, p.stack + amount)
            self.save_chips([p])
            return p.stack
        new = add_chips(tg_id, amount)
        if new is not None:
            self.profiles.setdefault(tg_id, {})["chips"] = new
        return new

    def buy(self, tg_id, skin_id: int) -> str | None:
        sk = self.skins.get(skin_id)
        if not sk or not sk["is_active"] or sk["owner_tg_id"] is not None:
            return "Скин не продаётся"
        if sk["price"] == 0:
            return None  # бесплатный — доступен всем
        p = self.player_of(tg_id)
        if p:
            if self.status == "betting" and p.in_hand and not p.folded:
                return "Покупки — между раздачами (или после фолда)"
            if p.stack < sk["price"]:
                return "Недостаточно фишек"
        error = buy_skin(tg_id, skin_id, sk["price"], charge_db=p is None)
        if error:
            return error
        if p:
            p.stack -= sk["price"]
            self.save_chips([p])
        else:
            self.profiles.pop(tg_id, None)
            self.connect_profile(tg_id)
        return None

    def connect_profile(self, tg_id):
        if tg_id is not None and tg_id not in self.profiles:
            profile = get_poker_profile(tg_id)
            if profile:
                self.profiles[tg_id] = profile

    # ---------- служебное ----------
    def player_of(self, tg_id) -> Player | None:
        return next((p for p in self.players if p.tg_id == tg_id), None)

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

    def alert(self, tg_id, message):
        for sid, t in list(self.sids.items()):
            if t == tg_id:
                socketio.emit("alert", {"message": message}, to=sid, namespace=NS)

    # ---------- подключения ----------
    def connect(self, sid, tg_id):
        self.sids[sid] = tg_id
        self.offline_since.pop(tg_id, None)
        self.connect_profile(tg_id)

    def disconnect(self, sid) -> int | None:
        return self.sids.pop(sid, None)

    # ---------- вход / выход ----------
    def join(self, user: dict) -> str | None:
        tg_id = int(user["id"])
        if self.player_of(tg_id):
            return "Вы уже за столом"
        if len(self.players) >= self.cfg["max_players"]:
            return "Стол заполнен"
        profile = get_poker_profile(tg_id)
        if not profile:
            return "Пользователь не найден"
        self.profiles[tg_id] = profile
        if profile["chips"] <= 0:
            return "Нет фишек — заберите бонус"
        self.players.append(Player(
            tg_id=tg_id,
            name=user.get("username") or f"id{tg_id}",
            photo_url=user.get("photo_url") or "",
            stack=profile["chips"],
            back_skin=profile["back_skin"] if self.can_use_skin(tg_id, "back", profile["back_skin"]) else "classic",
            front_skin=profile["front_skin"] if self.can_use_skin(tg_id, "front", profile["front_skin"]) else "classic",
            ready=self.running,  # игра уже идёт — сядет в следующую раздачу без «Готов»
        ))
        return None

    def leave(self, tg_id, reason="Вышел") -> str | None:
        p = self.player_of(tg_id)
        if not p:
            return "Вы не за столом"
        self._remove(p, reason)
        self.maybe_start()  # оставшиеся могли быть уже готовы
        return None

    def _remove(self, p: Player, reason: str):
        self.players.remove(p)
        self.offline_since.pop(p.tg_id, None)
        self.save_chips([p])
        self.profiles.pop(p.tg_id, None)
        # ушёл посреди раздачи = фолд; поставленные фишки остаются в банке
        if self.status == "betting" and p.in_hand and not p.folded:
            p.folded = True
            p.last = reason
            if len(self.live()) == 1:
                self.finish()
            elif self.deadline and self.hand[self.cur] is p:
                self.next()

    def set_ready(self, tg_id, ready: bool) -> str | None:
        p = self.player_of(tg_id)
        if not p:
            return "Вы не за столом"
        if self.status == "betting":
            return None
        p.ready = bool(ready)
        self.maybe_start()
        return None

    def maybe_start(self):
        """
        Первая раздача — когда все за столом нажали «Готов» (минимум двое).
        На итогах раздачи: все нажали «Готов» — следующая начинается сразу, не дожидаясь таймера.
        """
        if self.status == "betting" or len(self.players) < 2 or not all(p.ready for p in self.players):
            return
        self.running = True
        self.start_hand()

    def stop_game(self):
        self.running = False
        self.status, self.stage, self.next_hand_at = "waiting", "", None
        self.hand, self.board, self.winners = [], [], []
        for p in self.players:
            p.ready = False
            p.in_hand = False

    # ---------- раздача ----------
    def start_hand(self):
        if not self.running or self.status == "betting":
            return
        self.next_hand_at = None
        if self.pending_cfg:  # изменения из админки вступают в силу с этой раздачи
            self._cfg, self.pending_cfg = self.pending_cfg, None
        online = self.online_ids()
        for p in list(self.players):
            if p.stack <= 0:
                self.alert(p.tg_id, "Фишки закончились — заберите бонус и присоединяйтесь снова")
                self._remove(p, "Банкрот")
            elif p.timeouts >= MAX_TIMEOUTS:
                self.alert(p.tg_id, "Вы пропустили несколько ходов и были убраны из-за стола")
                self._remove(p, "AFK")
            elif p.tg_id not in online:
                self._remove(p, "Отключился")
        players = list(self.players)
        if len(players) < 2:
            self.stop_game()
            self.broadcast()
            return

        self.hand_no += 1
        self.status, self.stage = "betting", "preflop"
        self.board, self.winners, self.deadline = [], [], None
        self.deck = [r + s for s in "shdc" for r in RANKS]
        random.shuffle(self.deck)
        for p in players:
            p.cards = [self.deck.pop(), self.deck.pop()]
            p.bet = p.total = 0
            p.folded = p.all_in = p.acted = False
            p.in_hand = True
            p.ready = True
            p.last = ""
        self.hand = players
        # задник «случайное фото»: каждому такому игроку — своё фото на эту раздачу
        lucky = [p for p in players if self.is_gallery_back(p.back_skin)]
        for p in players:
            p.gallery_photo = None
        if lucky:
            try:
                ids = random_gallery_photo_ids(len(lucky))
            except Exception as e:
                print(f"Покер: не удалось выбрать фото галереи: {e}")
                ids = []
            for i, p in enumerate(lucky):
                p.gallery_photo = ids[i % len(ids)] if ids else None

        n = len(players)
        self.dealer_idx = (self.dealer_idx + 1) % n
        di = self.dealer_idx
        front = self.profiles.get(players[di].tg_id, {}).get("front_skin", "classic")
        self.table_front = front if self.can_use_skin(players[di].tg_id, "front", front) else "classic"
        if n == 2:  # хедз-ап: дилер ставит малый блайнд и ходит первым на префлопе
            sb, bb = di, (di + 1) % n
        else:
            sb, bb = (di + 1) % n, (di + 2) % n
        sb_amount, bb_amount = self.cfg["small_blind"], self.cfg["big_blind"]
        self.post(players[sb], sb_amount)
        self.post(players[bb], bb_amount)
        self.cur_bet, self.min_raise = bb_amount, bb_amount
        self.cur = bb
        self.next()

    def post(self, p: Player, amount: int):
        amount = min(amount, p.stack)
        p.stack -= amount
        p.bet += amount
        p.total += amount
        if p.stack == 0:
            p.all_in = True

    def action(self, tg_id, kind: str, amount=None, auto=False) -> str | None:
        if self.status != "betting" or not self.deadline:
            return "Сейчас нет вашего хода"
        p = self.hand[self.cur]
        if p.tg_id != tg_id or self.player_of(tg_id) is not p:
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
        self.cur_bet, self.min_raise = 0, self.cfg["big_blind"]
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
        self.cur = (self.dealer_idx + 1) % n
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
        for p in self.players:
            p.ready = False  # на итогах можно снова нажать «Готов», чтобы не ждать таймер
        self.save_chips(self.players)
        result = {"hand_no": self.hand_no, "pot": total, "winners": self.winners}
        self.history.append(result)
        socketio.emit("hand_result", result, namespace=NS)
        # следующая раздача начнётся сама
        delay = self.cfg["showdown_time"]
        self.next_hand_at = time.time() + delay
        socketio.start_background_task(self._delayed, self.gen, delay, self.start_hand)
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
        turn_time = self.cfg["turn_time"]
        self.deadline = time.time() + turn_time
        socketio.start_background_task(self._delayed, self.gen, turn_time, self._on_timeout)

    def _on_timeout(self):
        p = self.hand[self.cur]
        self.action(p.tg_id, "fold" if self.cur_bet - p.bet else "check", auto=True)

    def _delayed(self, gen, delay, fn):
        socketio.sleep(delay)
        with self.lock:
            if self.gen == gen:
                fn()

    def _kick_if_offline(self, tg_id):
        socketio.sleep(DISCONNECT_GRACE)
        with self.lock:
            since = self.offline_since.get(tg_id)
            # переподключился (или отключился ещё раз позже) — этот таймер уже не актуален
            if since is not None and time.time() - since >= DISCONNECT_GRACE - 0.5 and self.player_of(tg_id):
                self.leave(tg_id, "Отключился")
                self.broadcast()

    # ---------- бонус и настройки ----------
    def claim_bonus(self, tg_id) -> tuple[str | None, int]:
        p = self.player_of(tg_id)
        if p and self.status == "betting" and p.in_hand and not p.folded:
            return "Забрать бонус можно между раздачами", 0
        amount = self.cfg["bonus_amount"]
        result = claim_bonus(tg_id, amount, self.cfg["bonus_cooldown_hours"] * 3600, time.time(), add_to_chips=p is None)
        if result is None:
            return "Бонус ещё недоступен", 0
        self.profiles.setdefault(tg_id, {})["bonus_at"] = result["bonus_at"]
        if p:
            p.stack += amount
            self.save_chips([p])
        else:
            self.profiles[tg_id]["chips"] = result["chips"]
        return None, amount

    # ---------- состояние ----------
    def view(self, tg_id) -> dict:
        me = self.player_of(tg_id) if tg_id is not None else None
        live_count = len(self.live())
        online = self.online_ids()
        profile = self.profiles.get(tg_id, {}) if tg_id is not None else {}
        dealer = self.hand[self.dealer_idx] if self.hand and self.status != "waiting" else None
        players = []
        for p in self.players:
            in_hand = p.in_hand and self.status != "waiting"
            show = in_hand and p.cards and (
                p is me or (self.status == "showdown" and live_count > 1 and not p.folded))
            players.append({
                "id": str(p.tg_id), "name": p.name, "photo_url": p.photo_url,
                "stack": p.stack, "bet": p.bet if in_hand else 0, "folded": p.folded and in_hand,
                "all_in": p.all_in and in_hand, "in_hand": in_hand, "ready": p.ready,
                "online": p.tg_id in online,
            "offline_until": (self.offline_since[p.tg_id] + DISCONNECT_GRACE) if p.tg_id in self.offline_since else None,
                "last_action": p.last if in_hand else "", "is_dealer": p is dealer,
                "cards": p.cards if show else None,
                "back_skin": self.back_desc(p),
                "front_skin": self.skin_desc(p.front_skin, "front"),
            })
        to_act = str(self.hand[self.cur].tg_id) if self.status == "betting" and self.deadline else None
        cfg = self.cfg
        return {
            "status": self.status, "stage": self.stage if self.status == "betting" else "",
            "running": self.running, "hand_no": self.hand_no, "blinds": [cfg["small_blind"], cfg["big_blind"]],
            "pot": self.pot() if self.status != "waiting" else 0,
            "community": self.board, "current_bet": self.cur_bet, "min_raise_to": self.cur_bet + self.min_raise,
            "to_act": to_act, "deadline": self.deadline, "turn_time": cfg["turn_time"], "server_now": time.time(),
            "next_hand_at": self.next_hand_at, "winners": self.winners,
            "players": players, "max_players": cfg["max_players"],
            "table_skin": self.skin_desc(self.table_front, "front"), "is_admin": is_admin(tg_id),
            "me": str(me.tg_id) if me else None,
            "logged_in": tg_id is not None,
            "bank_chips": profile.get("chips"),
            "bonus_next_at": profile.get("bonus_at", 0), "bonus_amount": cfg["bonus_amount"],
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
    skins = None
    if user:
        tg_id = int(user["id"])
        profile = get_poker_profile(tg_id)
        if profile:
            with table.lock:
                skins = {"front": table.skin_desc(profile["front_skin"], "front"),
                         "back": table.skin_desc(profile["back_skin"], "back")}
    return render_template("poker.html", user=user, skins=skins, is_admin=bool(user) and is_admin(user["id"]))


def _tg_id():
    user = session.get("user")
    return int(user["id"]) if user else None


def _alert(message):
    emit("alert", {"message": message})


@socketio.on("connect", namespace=NS)
def poker_connect(auth=None):
    with table.lock:
        tg_id = _tg_id()
        table.connect(request.sid, tg_id)
        if table.player_of(tg_id):  # вернулся за стол — убрать значок «отключился»
            table.broadcast()


@socketio.on("disconnect", namespace=NS)
def poker_disconnect(*args):
    with table.lock:
        tg_id = table.disconnect(request.sid)
        seated = tg_id is not None and table.player_of(tg_id) is not None
        if seated and tg_id not in table.online_ids():
            table.offline_since[tg_id] = time.time()
            table.broadcast()
            socketio.start_background_task(table._kick_if_offline, tg_id)


@socketio.on("join_table", namespace=NS)
def poker_join_table(data=None):
    with table.lock:
        table.send_state(request.sid)
        for result in table.history:
            emit("hand_result", result)


@socketio.on("join_game", namespace=NS)
def poker_join_game(data=None):
    user = session.get("user")
    if not user:
        return _alert("Войдите через Telegram, чтобы играть")
    with table.lock:
        error = table.join(user)
        if error:
            return _alert(error)
        table.broadcast()


@socketio.on("leave_game", namespace=NS)
def poker_leave_game(data=None):
    tg_id = _tg_id()
    if tg_id is None:
        return
    with table.lock:
        error = table.leave(tg_id)
        if error:
            return _alert(error)
        table.connect(request.sid, tg_id)  # перечитать баланс из БД
        table.broadcast()


@socketio.on("set_ready", namespace=NS)
def poker_set_ready(data=None):
    tg_id = _tg_id()
    if tg_id is None:
        return _alert("Войдите через Telegram")
    with table.lock:
        error = table.set_ready(tg_id, (data or {}).get("ready", True))
        if error:
            return _alert(error)
        if table.status != "betting":  # если раздача началась, состояние уже разослано
            table.broadcast()


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


# HTTP-роуты скинов и админ-панели
from flask_server import poker_skins  # noqa: E402,F401
