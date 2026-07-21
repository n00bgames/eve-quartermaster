from __future__ import annotations

import re
from dataclasses import dataclass


QUANTITY_FIRST_RE = re.compile(r"^\s*(?P<qty>\d[\d,]*)\s*x?\s+(?P<name>.+?)\s*$", re.IGNORECASE)
QUANTITY_LAST_RE = re.compile(r"^\s*(?P<name>.+?)\s+(?:x\s*)?(?P<qty>\d[\d,]*)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedItemLine:
    original_text: str
    name: str
    quantity: int
    line_number: int


def normalize_item_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def parse_item_line(raw_line: str, line_number: int = 1) -> ParsedItemLine | None:
    line = raw_line.strip()
    if not line:
        return None
    quantity = 1
    name = line
    first = QUANTITY_FIRST_RE.match(line)
    last = QUANTITY_LAST_RE.match(line)
    if first:
        quantity = int(first.group("qty").replace(",", ""))
        name = first.group("name")
    elif last:
        quantity = int(last.group("qty").replace(",", ""))
        name = last.group("name")
    name = normalize_item_name(name)
    if not name or quantity < 1:
        return None
    return ParsedItemLine(line, name, quantity, line_number)


def parse_item_lines(text: str, merge_duplicates: bool = False) -> tuple[list[ParsedItemLine], list[dict[str, object]]]:
    rows = [row for index, line in enumerate(text.splitlines(), 1) if (row := parse_item_line(line, index))]
    grouped: dict[str, list[ParsedItemLine]] = {}
    for row in rows:
        grouped.setdefault(row.name.casefold(), []).append(row)
    duplicates = [
        {"name": group[0].name, "line_numbers": [row.line_number for row in group], "quantity": sum(row.quantity for row in group)}
        for group in grouped.values()
        if len(group) > 1
    ]
    if not merge_duplicates:
        return rows, duplicates
    merged = [
        ParsedItemLine(group[0].original_text, group[0].name, sum(row.quantity for row in group), group[0].line_number)
        for group in grouped.values()
    ]
    return merged, duplicates