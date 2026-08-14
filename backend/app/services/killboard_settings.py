from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AppSetting


SETTING_KEYS = {
    "enabled": "killboard_enabled",
    "sync_period_hours": "killboard_sync_period_hours",
    "lookback_days": "killboard_lookback_days",
    "request_delay_seconds": "killboard_request_delay_seconds",
    "max_pages": "killboard_max_pages",
}


def _raw(db: Session, name: str) -> str | None:
    row = db.get(AppSetting, SETTING_KEYS[name])
    return str(row.value) if row is not None else None


def killboard_settings(db: Session) -> dict[str, Any]:
    defaults = get_settings()
    raw_enabled = _raw(db, "enabled")
    values = {
        "enabled": defaults.killboard_enabled_default if raw_enabled is None else raw_enabled.strip().lower() in {"1", "true", "yes", "on"},
        "sync_period_hours": _int_setting(_raw(db, "sync_period_hours"), defaults.killboard_sync_period_hours_default, 1, 168),
        "lookback_days": _int_setting(_raw(db, "lookback_days"), defaults.killboard_lookback_days_default, 1, 3650),
        "request_delay_seconds": _float_setting(_raw(db, "request_delay_seconds"), defaults.killboard_request_delay_seconds_default, 0.2, 30.0),
        "max_pages": _int_setting(_raw(db, "max_pages"), defaults.killboard_max_pages_default, 1, 100),
    }
    return values


def update_killboard_settings(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    current = killboard_settings(db)
    next_values = {
        "enabled": bool(payload.get("enabled", current["enabled"])),
        "sync_period_hours": _bounded_int(payload.get("sync_period_hours", current["sync_period_hours"]), 1, 168, "sync_period_hours"),
        "lookback_days": _bounded_int(payload.get("lookback_days", current["lookback_days"]), 1, 3650, "lookback_days"),
        "request_delay_seconds": _bounded_float(payload.get("request_delay_seconds", current["request_delay_seconds"]), 0.2, 30.0, "request_delay_seconds"),
        "max_pages": _bounded_int(payload.get("max_pages", current["max_pages"]), 1, 100, "max_pages"),
    }
    for name, value in next_values.items():
        row = db.get(AppSetting, SETTING_KEYS[name])
        serialized = str(value).lower() if isinstance(value, bool) else str(value)
        if row is None:
            db.add(AppSetting(key=SETTING_KEYS[name], value=serialized))
        else:
            row.value = serialized
    return next_values


def _int_setting(raw: str | None, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(raw))) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _float_setting(raw: str | None, default: float, low: float, high: float) -> float:
    try:
        return max(low, min(high, float(raw))) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _bounded_int(value: Any, low: int, high: int, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not low <= parsed <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return parsed


def _bounded_float(value: Any, low: float, high: float, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not low <= parsed <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return parsed
