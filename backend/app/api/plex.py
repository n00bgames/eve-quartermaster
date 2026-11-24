from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.models.plex import PlexTransaction
from app.schemas.plex import PlexImportInput, PlexTransactionInput
from app.services.audit import record_audit_event
from app.services.permissions import can_view_section
from app.services.plex import ledger, market_data, utc

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


@router.post("/transactions/import")
def import_transactions(payload: PlexImportInput, user: User = Depends(require_plex), db: Session = Depends(get_db)):
    """Save a reviewed screenshot batch atomically under the normal account lock."""
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    rows = owned_rows(db, user)

    def key(row):
        # Wallet screenshots may omit seconds. Fees/notes aren't trade identity.
        return (utc(row.occurred_at).replace(second=0, microsecond=0), row.kind, row.quantity, row.unit_price)

    keys = {key(row) for row in rows}
    try:
        # Preserve the user's review order for equal timestamps, as for manual entries.
        for index, item in sorted(enumerate(payload.transactions), key=lambda pair: utc(pair[1].occurred_at)):
            identity = key(item)
            if identity in keys and not item.allow_duplicate:
                raise HTTPException(409, f"Import row {index + 1} is a possible duplicate. Nothing was imported. Refresh the ledger, or explicitly allow this duplicate after review.")
            keys.add(identity)
            row = PlexTransaction(owner_user_id=user.id, **item.model_dump(exclude={"allow_duplicate"}))
            rows.append(row)
            db.add(row)
        ledger(rows)
        # Allocate IDs in reviewed chronological order before final FIFO validation.
        db.flush()
        ledger(rows)
        record_audit_event(db, event_kind="plex_transaction_changed", title="PLEX ledger updated",
                           body=f"Imported {len(payload.transactions)} private wallet trades", actor_user=user)
        db.commit()
    except (ValueError, HTTPException) as exc:
        db.rollback()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(400, str(exc)) from None
    return {"ledger": ledger(owned_rows(db, user)), "imported": len(payload.transactions)}


@router.put("/transactions/{transaction_id}")
def edit_transaction(transaction_id: int, payload: PlexTransactionInput, user: User = Depends(require_plex), db: Session = Depends(get_db)):
    return save_transaction(db, user, payload, transaction_id)


@router.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, user: User = Depends(require_plex), db: Session = Depends(get_db)):
    return save_transaction(db, user, transaction_id=transaction_id, deleting=True)
