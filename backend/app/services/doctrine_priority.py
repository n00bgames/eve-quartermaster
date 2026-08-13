from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException


def _code_part(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", str(value).strip().upper()).strip("-")[:32]


def validate_priority_values(fields: list[Any], values: dict[str, Any], manual_code: str | None = None) -> tuple[dict[str, Any], str]:
    active = {field.key: field for field in fields if field.is_active}
    unknown = sorted(set(values) - set(active))
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown priority field(s): {', '.join(unknown)}")
    normalized: dict[str, Any] = {}
    code_parts: list[str] = []
    for field in sorted(active.values(), key=lambda row: (row.display_order, row.id or 0)):
        value = values.get(field.key)
        if value in (None, ""):
            if field.is_required:
                raise HTTPException(status_code=400, detail=f"{field.name} is required")
            continue
        if field.field_type == "select":
            option = next((row for row in field.options if row.is_active and row.value == str(value)), None)
            if option is None:
                raise HTTPException(status_code=400, detail=f"Invalid value for {field.name}")
            normalized[field.key] = option.value
            code_parts.append(_code_part(option.short_code or option.value))
        elif field.field_type == "number":
            try:
                normalized[field.key] = float(value)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=f"{field.name} must be a number") from exc
            code_parts.append(_code_part(normalized[field.key]))
        elif field.field_type == "boolean":
            if not isinstance(value, bool):
                raise HTTPException(status_code=400, detail=f"{field.name} must be true or false")
            normalized[field.key] = value
            code_parts.append("Y" if value else "N")
        else:
            normalized[field.key] = str(value).strip()
            code_parts.append(_code_part(value))
    final_code = (manual_code or "").strip() if manual_code is not None else "-".join(filter(None, code_parts))
    if not final_code:
        final_code = "STANDARD"
    return normalized, final_code[:120]
