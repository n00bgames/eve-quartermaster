from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.enums import AssetSource, LocationKind


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_kind: Mapped[LocationKind] = mapped_column(default=LocationKind.UNKNOWN, nullable=False)
    eve_location_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    system_id: Mapped[int | None] = mapped_column(ForeignKey("eve_systems.system_id"), index=True)
    parent_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    source: Mapped[AssetSource] = mapped_column(default=AssetSource.MANUAL, nullable=False)
    notes: Mapped[str | None] = mapped_column(String)

    parent: Mapped["Location | None"] = relationship(remote_side=[id], lazy="joined")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    ownership_entity_id: Mapped[int] = mapped_column(ForeignKey("ownership_entities.id"), nullable=False, index=True)
    eve_item_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("eve_types.type_id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), index=True)
    parent_asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), index=True)
    location_flag: Mapped[str | None] = mapped_column(String(80), index=True)
    is_singleton: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_blueprint_copy: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[AssetSource] = mapped_column(default=AssetSource.ESI, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    ownership_entity = relationship("OwnershipEntity")
    item_type = relationship("EveType")
    location = relationship("Location")
    parent_asset: Mapped["Asset | None"] = relationship(remote_side=[id])

