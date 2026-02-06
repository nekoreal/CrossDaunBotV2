from sqlalchemy import Column, Integer, String, BigInteger
from telegram_bot.tg_db import Base
from sqlalchemy.orm import relationship

class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True, index=True, unique=True, nullable=False, autoincrement=True)
    tg_id = Column(BigInteger, unique=True, nullable=False, index=True)

    msg_count = Column(Integer, default=0, nullable=False)
    photo_count = Column(Integer, default=0, nullable=False)
    video_count = Column(Integer, default=0, nullable=False)
    sticker_count = Column(Integer, default=0, nullable=False)
    nya_count = Column(Integer, default=0, nullable=False)

    msg_count_month = Column(Integer, default=0, nullable=False)
    photo_count_month = Column(Integer, default=0, nullable=False)
    video_count_month = Column(Integer, default=0, nullable=False)
    sticker_count_month = Column(Integer, default=0, nullable=False)
    nya_count_month = Column(Integer, default=0, nullable=False)


    at_user_tag = relationship("UserTagAssociation", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "tg_id": self.tg_id,
            "msg_count": self.msg_count,
            "photo_count": self.photo_count,
            "video_count": self.video_count,
            "sticker_count": self.sticker_count,
            "nya_count": self.nya_count,
            "msg_count_month": self.msg_count_month,
            "photo_count_month": self.photo_count_month,
            "video_count_month": self.video_count_month,
            "sticker_count_month": self.sticker_count_month,
            "nya_count_month": self.nya_count_month,
        }

    def __repr__(self):
        return f"<TelegramUser(tg_id={self.tg_id} )>"
