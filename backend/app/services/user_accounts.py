from datetime import datetime, timezone
from typing import Protocol


class RetirableUser(Protocol):
    id: int
    email: str
    display_name: str
    password_hash: str | None
    role: str
    timezone: str
    deleted_at: datetime | None


def retire_user_account(user: RetirableUser, deleted_at: datetime | None = None) -> None:
    """Remove login access and personal identifiers while preserving ledger history."""
    user.email = f"deleted-user-{user.id}@invalid.local"
    user.display_name = f"Deleted user {user.id}"
    user.password_hash = None
    user.role = "member"
    user.timezone = "UTC"
    user.deleted_at = deleted_at or datetime.now(timezone.utc)