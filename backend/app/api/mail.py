from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.esi import chunked, refresh_access_token, token_scopes
from app.db.session import get_db
from app.models import EsiToken, EveCharacter, User
from app.services.esi_client import EsiClient, resolve_names

router = APIRouter(prefix="/mail", tags=["mail"])

MAIL_READ_SCOPE = "esi-mail.read_mail.v1"
MAIL_SEND_SCOPE = "esi-mail.send_mail.v1"
MAIL_ORGANIZE_SCOPE = "esi-mail.organize_mail.v1"
MAIL_SCOPES = [MAIL_READ_SCOPE, MAIL_SEND_SCOPE, MAIL_ORGANIZE_SCOPE]
RESOLVABLE_MAIL_RECIPIENT_TYPES = {"alliance", "character", "corporation"}


class MailRecipientInput(BaseModel):
    recipient_id: int
    recipient_type: str = Field(pattern="^(alliance|character|corporation|mailing_list)$")


class MailSendRequest(BaseModel):
    recipient_names: str | None = None
    recipients: list[MailRecipientInput] = []
    subject: str = Field(min_length=1, max_length=1000)
    body: str = Field(min_length=1)
    approved_cost: int = Field(default=0, ge=0)


def _mail_token_for_current_user(db: Session, token_id: int, current_user: User) -> tuple[EsiToken, EveCharacter]:
    token = db.get(EsiToken, token_id)
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Linked character token was not found")
    if token.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="EVE mail can only be opened by the account that linked the character")
    character = db.get(EveCharacter, token.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="Linked character was not found")
    return token, character


def _require_mail_scope(token: EsiToken, scope: str, action: str) -> None:
    if scope not in token_scopes(token):
        raise HTTPException(status_code=400, detail=f"{action} requires {scope}. Re-link this character through EVE SSO after enabling that scope on the EVE developer app.")


async def _authenticated_mail_client(db: Session, token: EsiToken) -> EsiClient:
    access_token = await refresh_access_token(token)
    db.commit()
    return EsiClient(access_token=access_token)


async def _id_names(client: EsiClient, ids: list[int]) -> dict[int, str]:
    clean_ids = sorted({int(value) for value in ids if value})
    if not clean_ids:
        return {}
    names: dict[int, str] = {}
    for batch in chunked(clean_ids, 1000):
        try:
            rows = await client.post("/universe/names/", batch)
        except HTTPException:
            rows = []
            for entity_id in batch:
                try:
                    rows.extend(await client.post("/universe/names/", [entity_id]) or [])
                except HTTPException:
                    continue
        for row in rows or []:
            if row.get("id") is not None and row.get("name"):
                names[int(row["id"])] = row["name"]
    return names


def _mail_entity_ids(row: dict[str, Any]) -> list[int]:
    ids: list[int] = []
    if row.get("from") is not None:
        ids.append(int(row["from"]))
    for recipient in row.get("recipients") or []:
        if recipient.get("recipient_type") in RESOLVABLE_MAIL_RECIPIENT_TYPES and recipient.get("recipient_id") is not None:
            ids.append(int(recipient["recipient_id"]))
    return ids


def _enrich_mail_row(row: dict[str, Any], names: dict[int, str]) -> dict[str, Any]:
    enriched = dict(row)
    from_id = enriched.get("from")
    if from_id is not None:
        enriched["from_name"] = names.get(int(from_id), f"Character {from_id}")
    recipients = []
    for recipient in enriched.get("recipients") or []:
        next_recipient = dict(recipient)
        recipient_id = next_recipient.get("recipient_id")
        if recipient_id is not None:
            next_recipient["name"] = names.get(int(recipient_id), str(recipient_id))
        recipients.append(next_recipient)
    enriched["recipients"] = recipients
    return enriched


def _recipient_type_from_category(category: str) -> str | None:
    return {
        "alliances": "alliance",
        "characters": "character",
        "corporations": "corporation",
    }.get(category)


async def _resolve_recipients(recipient_names: str | None) -> list[dict[str, Any]]:
    names = [value.strip() for value in re.split(r"[,;\n]+", recipient_names or "") if value.strip()]
    if not names:
        return []
    resolved = await resolve_names(names)
    recipients: list[dict[str, Any]] = []
    for category, rows in resolved.items():
        recipient_type = _recipient_type_from_category(category)
        if recipient_type is None:
            continue
        for row in rows:
            if row.get("id") is not None:
                recipients.append({"recipient_id": int(row["id"]), "recipient_type": recipient_type})
    return recipients


@router.get("/characters")
async def mail_characters(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    tokens = db.scalars(
        select(EsiToken)
        .where(EsiToken.user_id == current_user.id)
        .where(EsiToken.revoked_at.is_(None))
        .order_by(EsiToken.created_at.desc())
    ).all()
    rows: list[dict[str, Any]] = []
    for token in tokens:
        character = db.get(EveCharacter, token.character_id)
        if character is None:
            continue
        scopes = token_scopes(token)
        rows.append(
            {
                "token_id": token.id,
                "character_id": character.character_id,
                "character_name": character.name,
                "can_read": MAIL_READ_SCOPE in scopes,
                "can_send": MAIL_SEND_SCOPE in scopes,
                "can_organize": MAIL_ORGANIZE_SCOPE in scopes,
                "missing_mail_scopes": [scope for scope in MAIL_SCOPES if scope not in scopes],
            }
        )
    return rows


@router.get("/{token_id}/headers")
async def mail_headers(
    token_id: int,
    last_mail_id: int | None = None,
    labels: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    token, character = _mail_token_for_current_user(db, token_id, current_user)
    _require_mail_scope(token, MAIL_READ_SCOPE, f"Reading EVE mail for {character.name}")
    client = await _authenticated_mail_client(db, token)
    params: dict[str, Any] = {}
    if last_mail_id is not None:
        params["last_mail_id"] = last_mail_id
    if labels:
        params["labels"] = labels
    rows = await client.get(f"/characters/{character.character_id}/mail/", params=params)
    rows = list(rows or [])[:limit]
    names = await _id_names(client, [entity_id for row in rows for entity_id in _mail_entity_ids(row)])
    return [_enrich_mail_row(row, names) for row in rows]


@router.get("/{token_id}/messages/{mail_id}")
async def mail_message(
    token_id: int,
    mail_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    token, character = _mail_token_for_current_user(db, token_id, current_user)
    _require_mail_scope(token, MAIL_READ_SCOPE, f"Reading EVE mail for {character.name}")
    client = await _authenticated_mail_client(db, token)
    row = await client.get(f"/characters/{character.character_id}/mail/{mail_id}/")
    names = await _id_names(client, _mail_entity_ids(row or {}))
    return _enrich_mail_row(row or {}, names)


@router.put("/{token_id}/messages/{mail_id}/read")
async def mark_mail_read(
    token_id: int,
    mail_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    token, character = _mail_token_for_current_user(db, token_id, current_user)
    _require_mail_scope(token, MAIL_ORGANIZE_SCOPE, f"Marking EVE mail read for {character.name}")
    client = await _authenticated_mail_client(db, token)
    await client.put(f"/characters/{character.character_id}/mail/{mail_id}/", {"read": True})
    return {"status": "read"}


@router.post("/{token_id}/send")
async def send_mail(
    token_id: int,
    request: MailSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    token, character = _mail_token_for_current_user(db, token_id, current_user)
    _require_mail_scope(token, MAIL_SEND_SCOPE, f"Sending EVE mail from {character.name}")
    client = await _authenticated_mail_client(db, token)
    recipients = [recipient.model_dump() for recipient in request.recipients]
    recipients.extend(await _resolve_recipients(request.recipient_names))
    unique_recipients = list({(row["recipient_type"], row["recipient_id"]): row for row in recipients}.values())
    if not unique_recipients:
        raise HTTPException(status_code=400, detail="At least one EVE mail recipient is required")
    mail_id = await client.post(
        f"/characters/{character.character_id}/mail/",
        {
            "approved_cost": request.approved_cost,
            "body": request.body,
            "recipients": unique_recipients,
            "subject": request.subject,
        },
    )
    return {"status": "sent", "mail_id": mail_id, "recipients": unique_recipients}
