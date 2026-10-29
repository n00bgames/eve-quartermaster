"""Short-lived, single-use browser-bound EVE account sign-in attempts."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class AccountSsoAttempt(Base):
    __tablename__ = 'account_sso_attempts'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    browser_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_verifier: Mapped[str] = mapped_column(Text, nullable=False)
    invite_id: Mapped[int | None] = mapped_column(ForeignKey('user_invites.id'))
    remember_me: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
