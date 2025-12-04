from sqlalchemy import Column, Integer, String, BigInteger
from telegram_bot.tg_db import Base
from sqlalchemy.orm import relationship

class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True, index=True, unique=True, nullable=False, autoincrement=True)
    tg_id = Column(BigInteger, unique=True, nullable=False, index=True)

    at_user_tag = relationship("UserTagAssociation", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "tg_id": self.tg_id,
        }

    def __repr__(self):
        return f"<TelegramUser(tg_id={self.tg_id} )>"
