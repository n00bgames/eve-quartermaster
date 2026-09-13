from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class EveSystemObject(Base):
    """Public, system-relative positions in metres. Never stores private structures."""
    __tablename__ = "eve_system_objects"
    object_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(255))
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    z: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(12), default="sde")


class SystemObjectSync(Base):
    __tablename__ = "system_object_syncs"
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id"), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    message: Mapped[str] = mapped_column(String(255))


class NavigationStructure(Base):
    """ESI structure position authorized for one token, never shared across users."""
    __tablename__ = "navigation_structures"
    token_id: Mapped[int] = mapped_column(ForeignKey("esi_tokens.id", ondelete="CASCADE"), primary_key=True)
    structure_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("eve_systems.system_id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    z: Mapped[float | None] = mapped_column(Float)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
