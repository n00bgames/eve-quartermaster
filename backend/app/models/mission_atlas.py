"""Public NPC agent directory imported from the SDE."""
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class EveAgent(Base):
    __tablename__ = "eve_agents"
    agent_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    corporation_id: Mapped[int] = mapped_column(Integer, index=True)
    corporation_name: Mapped[str] = mapped_column(String(255))
    faction_id: Mapped[int | None] = mapped_column(Integer, index=True)
    division_id: Mapped[int | None] = mapped_column(Integer, index=True)
    level: Mapped[int] = mapped_column(Integer, index=True)
    agent_type_id: Mapped[int | None] = mapped_column(Integer)
    is_locator: Mapped[bool] = mapped_column(Boolean, default=False)
    location_id: Mapped[int | None] = mapped_column(Integer)
    system_id: Mapped[int | None] = mapped_column(Integer, index=True)
