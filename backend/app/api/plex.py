from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.models.plex import PlexTransaction
from app.schemas.plex import PlexTransactionInput
from app.services.audit import record_audit_event
from app.services.permissions import can_view_section
from app.services.plex import ledger, market_data

router = APIRouter(prefix="/plex", tags=["plex"])


def require_plex(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not can_view_section(current_user, "plex", db):
        raise HTTPException(403, "PLEX Tracker access is required")
    return current_user


def owned_rows(db, user):
    return list(db.scalars(select(PlexTransaction).where(PlexTransaction.owner_user_id == user.id)).all())


@router.get("/ledger")
def get_ledger(user: User = Depends(require_plex), db: Session = Depends(get_db)):
    return ledger(owned_rows(db, user))


@router.get("/market")
async def get_market(user: User = Depends(require_plex), db: Session = Depends(get_db)):
    return await market_data(db)


@router.get("/history")
async def get_history(user: User = Depends(require_plex), db: Session = Depends(get_db)):
    return await market_data(db, "history")


def save_transaction(db, user, payload=None, transaction_id=None, deleting=False):
    # Serialize mutations for this account before rebuilding its chronological FIFO inventory.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    rows = owned_rows(db, user)
    row = next((r for r in rows if r.id == transaction_id), None) if transaction_id else None
    if transaction_id and row is None:
        raise HTTPException(404, "PLEX transaction not found")
    if deleting:
        rows.remove(row)
        db.delete(row)
    elif row:
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
    else:
        row = PlexTransaction(owner_user_id=user.id, **payload.model_dump())
        rows.append(row)
        db.add(row)
    try:
        ledger(rows)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from None
    record_audit_event(db, event_kind="plex_transaction_changed", title="PLEX ledger updated",
                       body="Private transaction deleted" if deleting else "Private transaction saved", actor_user=user)
    db.commit()
    return ledger(owned_rows(db, user))


@router.post("/transactions")
def create_transaction(payload: PlexTransactionInput, user: User = Depends(require_plex), db: Session = Depends(get_db)):
    return save_transaction(db, user, payload)


@router.put("/transactions/{transaction_id}")
def edit_transaction(transaction_id: int, payload: PlexTransactionInput, user: User = Depends(require_plex), db: Session = Depends(get_db)):
    return save_transaction(db, user, payload, transaction_id)


@router.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, user: User = Depends(require_plex), db: Session = Depends(get_db)):
    return save_transaction(db, user, transaction_id=transaction_id, deleting=True)
