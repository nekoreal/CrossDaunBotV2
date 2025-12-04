from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from .. import Base

class UserTagAssociation(Base):
    __tablename__ = "user_tag_association"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("telegram_users.id"))
    tag_id = Column(Integer, ForeignKey("telegram_tags.id"))

    user = relationship("TelegramUser", back_populates="at_user_tag")
    tag = relationship("TelegramTag", back_populates="at_user_tag")

    __table_args__ = (UniqueConstraint("user_id", "tag_id", name="_user_tag_uc"),)

    def __repr__(self):
        return f"<UserTagAssociation(user_id={self.user_id}, tag_id={self.tag_id})>"