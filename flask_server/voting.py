import time
from dataclasses import dataclass
from threading import Lock
from flask import Blueprint, request, session, redirect, url_for, render_template
from flask_socketio import emit, disconnect

from telegram_bot.tg_db.db_controllers.photo_controller import (
    get_all_categories_names,
    move_photo_to_category,
    get_random_photo_url
)
from dashboard import socketio


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
        self.winning_category: str = None
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

    def remove_voter_by_sid(self, sid: str):
        with self._lock:
            for ind, user in enumerate(self.users):
                if user.sid == sid:
                    if user.vote:
                        self.voted_counts = max(0, self.voted_counts - 1)
                        for cat in self.categories:
                            if cat.name == user.vote:
                                cat.votes = max(0, cat.votes - 1)
                                break
                    self.users.pop(ind)  # Удаляем по индексу, а не по объекту
                    break

    def add_voter(self, new_user: User):
        with self._lock:
            for ind, user in enumerate(self.users):
                if new_user.tg_id == user.tg_id:
                    try:
                        disconnect(user.sid)
                    except Exception:
                        pass
                    new_user.vote = user.vote  # Сохраняем прошлый голос при переподключении
                    self.users[ind] = new_user
                    return
            self.users.append(new_user)

    def change_status(self, new_status: str):
        self.status = new_status

    def update_categories(self):
        self.categories = [CategoryPoll(name=cat, votes=0) for cat in get_all_categories_names()]

    def start_poll(self):
        with self._lock:
            self.is_started = True
            self.results = {}
            self.change_status("waiting")

    def start_round(self, photo_id: int, photo_url: str = None):
        with self._lock:
            self.winning_category = None
            self.photo_id = photo_id
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
            results = {cat.name: {"count": cat.votes, "photo_urls": []} for cat in self.categories}
            
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
 
            """if self.winning_category and self.photo_id and max_votes > 0:
                try:
                    move_photo_to_category(self.photo_id, winning_category)
                except Exception:
                    pass"""

        socketio.emit("poll_state", self.data_poll_state())

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
            "status": self.status,
            "round": self.round,
            "photo_url": self.photo_url,
            "categories": [c.name for c in self.categories],
            "voted": self.voted_counts,
            "total": len(self.users),
            "results": self.results,
            "end_time": self.end_time  # Передаем точное время окончания
        }


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
        return render_template("vote.html", user=session.get("user"))
    return redirect(url_for("entry_telegram_bp.home"))


@voting_bp.route("/poll/start")
def start_poll():
    user = session.get("user")
    if user and user.get("is_moder"):
        poll.start_poll()
        return redirect(url_for("voting_bp.poll_page"))
    return "Ошибка авторизации", 400


@voting_bp.route("/poll/stop")
def stop_poll():
    user = session.get("user")
    if user and user.get("is_moder"):
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
    poll.add_voter(new_user)

    emit("poll_state", poll.data_poll_state())
    socketio.emit("update_voted_count", {
        "voted": poll.voted_counts,
        "total": len(poll.users)
    })


@socketio.on("disconnect")
def handle_disconnect():
    poll.remove_voter_by_sid(request.sid)
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
        
        poll.start_round(photo_id, photo_url)
        socketio.start_background_task(
            handle_end_round, 
            round_num=poll.round, 
            timeout=poll.timer
        )


@socketio.on("moder_end_round")
def handle_moder_end_round(data=None):
    user_data = session.get("user")
    if user_data and user_data.get("is_moder"):
        poll.end_round()