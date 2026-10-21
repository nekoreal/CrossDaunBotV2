from sqlalchemy import Column, Integer, String, BigInteger, Boolean, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from telegram_bot.tg_db import Base


class PokerSkin(Base):
    """Скин карт: kind='front' (лицо) или 'back' (задник). Картинки лежат в S3-бакете скинов."""
    __tablename__ = "poker_skins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String(10), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    price = Column(Integer, default=0, nullable=False)
    # личный задник, загруженный игроком: виден всем, но выбрать его может только владелец
    owner_tg_id = Column(BigInteger, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)  # False — скрыт из магазина
    # JSON: back — {"image": key}; front — {"images": {"K": key, ...}, "colors": {"s":..}, "bg": "#fff"}
    data = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PokerSkinOwner(Base):
    __tablename__ = "poker_skin_owners"
    __table_args__ = (UniqueConstraint("tg_id", "skin_id", name="uq_skin_owner"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_id = Column(BigInteger, nullable=False, index=True)
    skin_id = Column(Integer, ForeignKey("poker_skins.id", ondelete="CASCADE"), nullable=False)


class PokerSetting(Base):
    """Настройки стола, которые админ меняет из панели (ключ -> целое число)."""
    __tablename__ = "poker_settings"

    key = Column(String(50), primary_key=True)
    value = Column(Integer, nullable=False)
