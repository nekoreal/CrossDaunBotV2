from sqlalchemy import Column, Integer, Date, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import date
from .. import Base


class DailyStatistic(Base):
    """Дневная статистика пользователя (в день - одна строка на пользователя)"""
    __tablename__ = "daily_statistics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign key на пользователя
    user_id = Column(Integer, ForeignKey("telegram_users.id"), nullable=False, index=True)
    
    # Дата статистики
    date = Column(Date, nullable=False, index=True)
    
    # Счетчики контента за день
    msg_count = Column(Integer, default=0, nullable=False)
    photo_count = Column(Integer, default=0, nullable=False)
    video_count = Column(Integer, default=0, nullable=False)
    sticker_count = Column(Integer, default=0, nullable=False)
    nya_count = Column(Integer, default=0, nullable=False)
    
    # Проценты (рассчитываются автоматически при запросе)
    msg_percentage = Column(Float, default=0, nullable=False)
    photo_percentage = Column(Float, default=0, nullable=False)
    video_percentage = Column(Float, default=0, nullable=False)
    sticker_percentage = Column(Float, default=0, nullable=False)
    nya_percentage = Column(Float, default=0, nullable=False)
    
    # Гарантируем одну запись в день на пользователя
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='uq_user_date'),
    )

    @property
    def total(self):
        return self.msg_count + self.photo_count + self.video_count + self.sticker_count + self.nya_count

    def calculate_percentages(self):
        """Рассчитывает проценты контента"""
        total = self.msg_count + self.photo_count + self.video_count + self.sticker_count + self.nya_count
        
        if total == 0:
            self.msg_percentage = 0
            self.photo_percentage = 0
            self.video_percentage = 0
            self.sticker_percentage = 0
            self.nya_percentage = 0
        else:
            self.msg_percentage = (self.msg_count / total) * 100
            self.photo_percentage = (self.photo_count / total) * 100
            self.video_percentage = (self.video_count / total) * 100
            self.sticker_percentage = (self.sticker_count / total) * 100
            self.nya_percentage = (self.nya_count / total) * 100

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat(),
            "msg_count": self.msg_count,
            "photo_count": self.photo_count,
            "video_count": self.video_count,
            "sticker_count": self.sticker_count,
            "nya_count": self.nya_count,
            "msg_percentage": round(self.msg_percentage, 2),
            "photo_percentage": round(self.photo_percentage, 2),
            "video_percentage": round(self.video_percentage, 2),
            "sticker_percentage": round(self.sticker_percentage, 2),
            "nya_percentage": round(self.nya_percentage, 2),
            "total_count": self.msg_count + self.photo_count + self.video_count + self.sticker_count + self.nya_count,
        }

    def __repr__(self):
        return f"<DailyStatistic(user_id={self.user_id}, date={self.date}, total={self.msg_count + self.photo_count + self.video_count + self.sticker_count + self.nya_count})>"
