
from sqlalchemy import Column, ForeignKey, Integer, String, BigInteger, Boolean
from telegram_bot.tg_db import Base
from sqlalchemy.orm import relationship

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True, unique=True, nullable=False, autoincrement=True)
    name = Column(String(100, collation="utf8mb4_bin"), unique=True, nullable=False) 

    photo = relationship("Photo", back_populates="category" )

    def to_dict(self):
        return { 
            "id": self.id,
            "name": self.name
        }

    def __repr__(self):
        return f"<Category(id={self.id}, name={self.name})>"


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True, unique=True, nullable=False, autoincrement=True)
    tg_id = Column(BigInteger, unique=False, nullable=False )
    file_path = Column(String(1000, collation="utf8mb4_bin"), unique=True, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), index=True)

    category = relationship("Category", back_populates="photo")

    def to_dict(self):
        return {  
            "id": self.id,
            "tg_id": self.tg_id,
            "file_path": self.file_path,
            "category_id": self.category_id,
            "category": self.category.to_dict() if self.category else None,
        }

    def __repr__(self):
        return f"<Photo(tg_id={self.tg_id}, file_path={self.file_path}, category_id={self.category_id})>"
