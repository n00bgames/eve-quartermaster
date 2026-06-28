from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.enums import OwnerKind


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), default="member", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)



class UserInvite(Base):
    __tablename__ = "user_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    accepted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by_user: Mapped[User] = relationship(foreign_keys=[created_by_user_id])
    accepted_by_user: Mapped[User | None] = relationship(foreign_keys=[accepted_by_user_id])

class EveAlliance(Base):
    __tablename__ = "eve_alliances"

    id: Mapped[int] = mapped_column(primary_key=True)
    alliance_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ticker: Mapped[str | None] = mapped_column(String(20))


class EveCorporation(Base):
    __tablename__ = "eve_corporations"

    id: Mapped[int] = mapped_column(primary_key=True)
    corporation_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ticker: Mapped[str | None] = mapped_column(String(20))
    alliance_id: Mapped[int | None] = mapped_column(ForeignKey("eve_alliances.id"))
    ceo_character_eve_id: Mapped[int | None] = mapped_column(Integer)
    member_count: Mapped[int | None] = mapped_column(Integer)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EveCharacter(Base):
    __tablename__ = "eve_characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    corporation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_corporations.id"))
    alliance_id: Mapped[int | None] = mapped_column(ForeignKey("eve_alliances.id"))
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    portrait_url: Mapped[str | None] = mapped_column(String(500))
    public_assets_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    corporation: Mapped[EveCorporation | None] = relationship()
    alliance: Mapped[EveAlliance | None] = relationship()
    owner_user: Mapped[User | None] = relationship()


class OwnershipEntity(Base):
    __tablename__ = "ownership_entities"
    __table_args__ = (
        UniqueConstraint("owner_kind", "character_id", "corporation_id", "alliance_id", "display_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_kind: Mapped[OwnerKind] = mapped_column(default=OwnerKind.MANUAL_GROUP, nullable=False)
    character_id: Mapped[int | None] = mapped_column(ForeignKey("eve_characters.id"))
    corporation_id: Mapped[int | None] = mapped_column(ForeignKey("eve_corporations.id"))
    alliance_id: Mapped[int | None] = mapped_column(ForeignKey("eve_alliances.id"))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(String)

    character: Mapped[EveCharacter | None] = relationship()
    corporation: Mapped[EveCorporation | None] = relationship()
    alliance: Mapped[EveAlliance | None] = relationship()





