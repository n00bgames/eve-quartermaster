"""Scoped management of saved battles; private reports remain creator-only."""
from datetime import datetime
from typing import Annotated, Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, or_
from app.models import BattleReportShare
from app.services.local_scan import corporations, now, utc
from app.services.permissions import ROLE_RANK, role_rank


class DeleteReportsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[Annotated[int, Field(strict=True, gt=0)]] = Field(default_factory=list, max_length=500)
    from_at: datetime | None = None
    to_at: datetime | None = None
    all_in_scope: bool = False
    scope: Literal["own", "managed"] = "own"
    corporation_id: int | None = Field(default=None, gt=0)
    created_before: datetime | None = None

    @model_validator(mode="after")
    def one_mode(self):
        dates = self.from_at is not None or self.to_at is not None
        if int(bool(self.ids)) + int(dates) + int(self.all_in_scope) != 1:
            raise ValueError("Choose report IDs, a complete date range, or all reports in scope.")
        validate_dates(self.from_at, self.to_at)
        return self


def validate_dates(start, end):
    if (start is None) != (end is None) or (start is not None and utc(start) >= utc(end)):
        raise ValueError("Choose a start before the end of the generation-date range.")


def management_scope(db, user, scope="managed"):
    own = BattleReportShare.created_by_user_id == user.id
    public = BattleReportShare.is_private.is_(False)
    rank = role_rank(user, db)
    if scope == "own":
        return own
    if rank >= ROLE_RANK["admin"]:
        return or_(own, public)
    if rank >= ROLE_RANK["director"]:
        return or_(own, and_(public, BattleReportShare.corporation_id.in_([c[0] for c in corporations(db, user)])))
    return own


def management_context(db, user):
    rank = role_rank(user, db)
    return {
        "corporations": [{"id": cid, "name": name} for cid, name in corporations(db, user)],
        "can_manage_others": rank >= ROLE_RANK["director"],
        "management_scope": "your reports and all public reports" if rank >= ROLE_RANK["admin"] else
            "your reports and public reports attributed to your linked corporations" if rank >= ROLE_RANK["director"] else "your reports",
    }


def filters(db, user, scope="own", corporation_id=None, from_at=None, to_at=None, created_before=None):
    try:
        validate_dates(from_at, to_at)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    at = now()
    result = [management_scope(db, user, scope), BattleReportShare.revoked_at.is_(None),
        or_(BattleReportShare.expires_at.is_(None), BattleReportShare.expires_at > at)]
    if corporation_id is not None:
        result.append(BattleReportShare.corporation_id == corporation_id)
    if from_at is not None:
        result.extend([BattleReportShare.created_at >= utc(from_at), BattleReportShare.created_at < utc(to_at)])
    if created_before is not None:
        result.append(BattleReportShare.created_at <= utc(created_before))
    return result


def delete_filters(db, user, payload):
    result = filters(db, user, payload.scope, payload.corporation_id, payload.from_at, payload.to_at, payload.created_before)
    if payload.ids:
        result.append(BattleReportShare.id.in_(payload.ids))
    return result
