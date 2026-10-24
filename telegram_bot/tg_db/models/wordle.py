from sqlalchemy import Column, Integer, BigInteger, Boolean, Text, Date, DateTime, UniqueConstraint
from telegram_bot.tg_db import Base


class WordleGame(Base):
    """Партия в слово дня: у каждого игрока одна на день."""
    __tablename__ = "wordle_games"
    __table_args__ = (UniqueConstraint("tg_id", "day", name="uq_wordle_day"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    guesses = Column(Text, default="[]", nullable=False)  # JSON-список слов по порядку
    solved = Column(Boolean, default=False, nullable=False)
    finished = Column(Boolean, default=False, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
