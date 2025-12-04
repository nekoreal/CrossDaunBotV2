import sqlalchemy
from sqlalchemy import Column, Integer, String, BigInteger,ForeignKey
from telegram_bot.tg_db import Base
from sqlalchemy.orm import relationship

class TelegramTag(Base):
    __tablename__ = "telegram_tags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False, unique=True)
    tag = Column(String(25), nullable=False, unique=True)

    at_user_tag = relationship("UserTagAssociation", back_populates="tag", cascade="all, delete-orphan")

    def to_dict(self):
        res = {
            "id": self.id,
            "tag": self.tag
        }
        return res

    def __repr__(self):
        return f"<Tag(tag={self.tag})>"
