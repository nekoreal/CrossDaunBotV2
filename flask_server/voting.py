import time
from dataclasses import dataclass
from threading import Lock
from flask import Blueprint, request, session, redirect, url_for, render_template
from flask_socketio import emit, disconnect
from telegram_bot.senders import send_telegram_clear_message
from config import FLASK_DOMAIN
from telegram_bot.tg_utils.user import get_username_by_tgid

from telegram_bot.tg_db.db_controllers.photo_controller import (
    get_all_categories_names,
    move_photo_to_category,
    get_random_photo_url,
    get_count_unsorted
)
from flask_server.dashboard import socketio


@dataclass
class User:
    sid: str
    tg_id: int
    username: str
    photo_url: str
    is_moder: bool
    vote: str = None


@dataclass
class CategoryPoll:
    name: str
    votes: int = 0


class Poll:
    def __init__(self):
        self.photo_author:str|None=None
        self.edit_date:str|None=None
        self.creator:int|None=None
        self.decision:str|None=None
        self.winning_category: str |None= None
        self.timer: int = 60
        self.end_time: float = 0  # Timestamp окончания раунда
        self.photo_url = None
        self.photo_id: int = None
        self.is_started = False
        self.status = "waiting"  # waiting, in_progress, results
        self.categories: list[CategoryPoll] = []
        self.voted_counts = 0
        self.round = 0
        self.users: list[User] = []
        self.results = {}
        self._lock = Lock()

    def remove_voter_by_sid(self, sid: str) -> bool:
        """Удаляет пользователя только в том случае, если SID совпадает с его ТЕКУЩИМ SID."""
        with self._lock:
            for ind, user in enumerate(self.users):
                if user.sid == sid:
                    if user.vote:
                        self.voted_counts = max(0, self.voted_counts - 1)
                        for cat in self.categories:
                            if cat.name == user.vote:
                                cat.votes = max(0, cat.votes - 1)
                                break
                    self.users.pop(ind)
                    return True
            return False

    def add_voter(self, new_user: User) -> str | None:
        """
        Обновляет или добавляет пользователя.
        Возвращает old_sid, если пользователя нужно принудительно отключить.
        """
        old_sid = None
        with self._lock:
            for user in self.users:
                if new_user.tg_id == user.tg_id:
                    old_sid = user.sid
                    # Сохраняем голос, если пользователь уже успел проголосовать
                    new_user.vote = user.vote
                    
                    # Обновляем данные пользователя на актуальные из новой вкладки
                    user.sid = new_user.sid
                    user.username = new_user.username
                    user.photo_url = new_user.photo_url
                    user.is_moder = new_user.is_moder
                    user.vote = new_user.vote
                    return old_sid
            
            # Если пользователя нет в списке — добавляем
            self.users.append(new_user)
            return None

    def change_status(self, new_status: str):
        self.status = new_status

    def update_categories(self):
        self.categories = [CategoryPoll(name=cat, votes=0) for cat in get_all_categories_names()]

    def start_poll(self):
        with self._lock:
            self.is_started = True
            self.results = {}
            self.change_status("waiting")

    def start_round(self,
                     photo_id: int,
                     photo_url: str = None, 
                     photo_author:str="deleted", 
                     edit_date:str="Неизвестно"):
        with self._lock: 
            self.decision=None
            self.winning_category = None
            self.photo_id = photo_id
            self.photo_author=photo_author
            self.edit_date=edit_date
            self.photo_url = photo_url
            self.results = {}
            self.change_status("in_progress")
            self.end_time = time.time() + self.timer  # Время завершения раунда
            
            for user in self.users:
                user.vote = None
                
            self.update_categories()
            self.round += 1
            self.voted_counts = 0
            
        socketio.emit("poll_state", self.data_poll_state())

    def vote(self, tg_id: int, category_name: str) -> bool:
        with self._lock:
            if self.status != "in_progress":
                return False

            for user in self.users:
                if user.tg_id == tg_id:
                    if user.vote is None:
                        if category_name not in [cat.name for cat in self.categories]:
                            return False
                        user.vote = category_name
                        self.voted_counts += 1
                        for category in self.categories:
                            if category.name == category_name:
                                category.votes += 1
                                break
                        return True
                    return False
            return False

    def end_round(self):
        with self._lock:
            if self.status != "in_progress":
                return

            self.change_status("results")
            results = {cat.name: {"count": cat.votes, "photo_urls": []} for cat in self.categories if cat.votes > 0}
            
            self.winning_category = None
            max_votes = -1

            for cat in self.categories:
                if cat.votes > max_votes:
                    max_votes = cat.votes
                    self.winning_category = cat.name

            for user in self.users:
                if user.vote and user.vote in results:
                    results[user.vote]["photo_urls"].append(user.photo_url)

            self.results = results 

        socketio.emit("poll_state", self.data_poll_state())

    def apply_moder_decision(self, category_name: str | None) -> bool:
        """Применяет выбор модератора (категория или None) и переводит в статус 'decision'."""
        with self._lock: 
            if self.status != "results":
                return False 
            self.winning_category = category_name 
            if (self.photo_id is not None) and (category_name is not None):
                try:
                    move_photo_to_category(self.photo_id, category_name)
                    pass
                except Exception as e:
                    print(f"Ошибка при перемещении фото {self.photo_id}: {e}") 

            self.decision=f"{category_name if category_name else 'Неотсортировано'}"
            self.change_status("decision")
            return True

    def stop_poll(self):
        with self._lock:
            self.winning_category = None
            self.results = {}
            self.is_started = False
            self.status = "waiting"
            self.categories = []
            self.voted_counts = 0
            self.round = 0
            self.users = []

    def is_voter(self, tg_id: int) -> bool:
        return any(user.tg_id == tg_id for user in self.users)

    def data_poll_state(self) -> dict:
        return { 
            "unsorted_count":get_count_unsorted(),
            "decision":self.decision,
            "status": self.status,
            "round": self.round,
            "photo_url": self.photo_url,
            "photo_author": self.photo_author,
            "edit_date": self.edit_date,
            "categories": [c.name for c in self.categories],
            "voted": self.voted_counts,
            "total": len(self.users),
            "results": self.results,
            "end_time": self.end_time  # Передаем точное время окончания
        }

def is_started_poll() -> bool:
    return poll.is_started

poll = Poll()
voting_bp = Blueprint('voting_bp', __name__)


def handle_end_round(round_num: int, timeout: int = 60):
    socketio.sleep(timeout)
    if poll.round == round_num and poll.status == "in_progress":
        poll.end_round()


@voting_bp.route("/poll")
def poll_page():
    user = session.get("user")
    if poll.is_started and user:
        return render_template("poll.html", user=session.get("user"))
    return redirect(url_for("entry_telegram_bp.home"))


@voting_bp.route("/poll/start")
def start_poll():
    user = session.get("user")
    if user and user.get("is_moder") and (poll.is_started==False):
        poll.start_poll()
        send_telegram_clear_message(f"Была начата сортировка\n\nПрисоедениться по ссылке \n\n{FLASK_DOMAIN+str(url_for("voting_bp.poll_page"))}")
        return redirect(url_for("voting_bp.poll_page"))
    return "Ошибка авторизации", 400


@voting_bp.route("/poll/stop")
def stop_poll():
    user = session.get("user")
    if user and (user.get("is_moder")):
        if poll.is_started:
            send_telegram_clear_message(f"Сортировка закончилась\n\nРаунд: {poll.round}")
        poll.stop_poll()
        return redirect(url_for("entry_telegram_bp.home"))
    return "Ошибка авторизации", 400

 

@socketio.on("join_poll")
def handle_join():
    user_data = session.get("user")
    if not user_data or not poll.is_started:
        return

    tg_id = user_data.get("id")
    new_user = User(
        sid=request.sid,
        tg_id=tg_id,
        username=user_data.get("username", "Anon"),
        photo_url=user_data.get("photo_url", ""),
        is_moder=user_data.get("is_moder", False)
    )
    
    # 1. Получаем старый SID (если открыта новая вкладка)
    old_sid = poll.add_voter(new_user)

    # 2. Кикаем старый сокет ВНЕ блокировки Lock
    if old_sid and old_sid != request.sid:
        try:
            disconnect(old_sid)
        except Exception:
            pass

    emit("poll_state", poll.data_poll_state())
    socketio.emit("update_voted_count", {
        "voted": poll.voted_counts,
        "total": len(poll.users)
    })


@socketio.on("disconnect")
def handle_disconnect(): 
    if poll.remove_voter_by_sid(request.sid):
         
        with poll._lock:
            should_end = (
                poll.status == "in_progress" 
                and len(poll.users) > 0 
                and poll.voted_counts >= len(poll.users)
            )
 
        if should_end:
            poll.end_round()
        else: 
            socketio.emit("update_voted_count", {
                "voted": poll.voted_counts,
                "total": len(poll.users)
            })


@socketio.on("submit_vote")
def handle_vote(data):
    user_data = session.get("user")
    if not user_data or poll.status != "in_progress":
        emit("alert", {"message": "Голосование недоступно"})
        return

    tg_id = user_data.get("id")
    category_name = data.get("category")

    if poll.vote(tg_id, category_name):
        emit("vote_success", {"category": category_name})
        if poll.voted_counts >= len(poll.users) and len(poll.users) > 0:
            poll.end_round()
        else:
            socketio.emit("update_voted_count", {
                "voted": poll.voted_counts,
                "total": len(poll.users)
            })
    else:
        emit("alert", {"message": "Не удалось засчитать голос"})


@socketio.on("moder_start_round")
def handle_start_round(data=None):
    user_data = session.get("user")
    if user_data and user_data.get("is_moder"):
        photo = get_random_photo_url(with_category=False)
        if not photo:
            emit("alert", {"message": "Нет доступных фото для голосования"})
            return

        photo_id = photo["id"]
        photo_url = photo["file_url"]
        edit_date = photo["edit_date"]
        photo_author = get_username_by_tgid(photo["tg_id"])
        
        poll.start_round(photo_id=photo_id, 
                         photo_url=photo_url,
                         edit_date=edit_date,
                         photo_author=photo_author)
        socketio.start_background_task(
            handle_end_round, 
            round_num=poll.round, 
            timeout=poll.timer
        )

@socketio.on("moder_decision")
def handle_moder_decision(data):
    user_data = session.get("user")
    if not user_data or not user_data.get("is_moder"):
        emit("alert", {"message": "Недостаточно прав"})
        return
 
    category_name = data.get("category") if data else None 

    if poll.apply_moder_decision(category_name): 
        socketio.emit("poll_state", poll.data_poll_state())
    else:
        emit("alert", {"message": "Не удалось применить решение модератора"})