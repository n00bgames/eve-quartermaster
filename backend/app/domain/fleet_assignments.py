"""Portable rules; no EQM, ORM, web-framework, or ESI dependencies."""
from dataclasses import dataclass
from typing import Iterable

SCHEMA_VERSION = "eqm.fleet-assignments.v1"
MAX_PILOTS = 500
MAX_SLOTS = 100

@dataclass(frozen=True)
class Principal:
    subject: str
    character_ids: frozenset[int]
    can_manage: bool = False

def parse_roster(text: str) -> tuple[list[str], list[str]]:
    """One name per line or tab-separated EVE roster with optional Name header."""
    names, duplicates, seen = [], [], set()
    column = 0
    for line in text.splitlines():
        cells = line.strip().split("\t")
        headers = [cell.strip().casefold() for cell in cells]
        labels = {"name", "character", "character name", "pilot"}
        if any(cell in labels for cell in headers):
            column = next(i for i, cell in enumerate(headers) if cell in labels)
            continue
        name = " ".join((cells[column] if column < len(cells) else cells[0]).split())
        if not name:
            continue
        if len(name) > 255 or any(ord(char) < 32 for char in name):
            raise ValueError("Each roster row must contain a character name of at most 255 characters")
        key = name.casefold()
        if key in seen:
            duplicates.append(name)
        else:
            seen.add(key)
            names.append(name)
        if len(names) > MAX_PILOTS:
            raise ValueError("A fleet may contain at most 500 pilots")
    return names, duplicates

def assignment_targets(requested: Iterable[int], available: Iterable[int]) -> list[int]:
    targets = list(dict.fromkeys(requested))
    if not targets or len(targets) > MAX_PILOTS:
        raise ValueError("Choose between 1 and 500 pilots")
    if not set(targets).issubset(set(available)):
        raise ValueError("Every selected pilot must belong to this operation")
    return targets

def may_view_assignment(principal: Principal, character_id: int | None, published: bool) -> bool:
    # Staff privileges never widen the personal view.
    return published and character_id is not None and character_id in principal.character_ids
