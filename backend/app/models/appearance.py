"""Per-account presentation and administrator-owned public branding."""
from sqlalchemy import ForeignKey, Integer, JSON, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class UserAppearance(Base):
    __tablename__ = "user_appearance"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    banner: Mapped[bytes | None] = mapped_column(LargeBinary)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

class SiteBranding(Base):
    __tablename__ = "site_branding"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    banner: Mapped[bytes | None] = mapped_column(LargeBinary)
    login_background: Mapped[bytes | None] = mapped_column(LargeBinary)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
