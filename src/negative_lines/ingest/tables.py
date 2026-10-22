"""Detect and merge table rows that printing wrapped over several physical rows.

Patent tables have narrow columns, so one logical row such as

    Examples 3 to 4 | Resin 1 (100 parts by weight) | PAG1 (10 parts by weight) | ...

arrives as three physical rows:

    Examples | Resin 1     | PAG1 (10 parts | ...
    3 to 4   | (100 parts  | by weight)     | ...
             | by weight)  |                | ...

Rules (deterministic, conservative):

A physical row continues the current group if it has at most as many cells
(shorter rows are padded with empty cells; Google Patents omits trailing empty
cells) and either

1. the group is *open*: some cell is unfinished (unbalanced "(", or ends with
   "-", "=", "/", "," or a connective such as "by", "of", "parts"), or
2. its first (label) cell is empty and no column holds a complete value in
   both rows (two numbers, a number and a dash, ...): that would be a new row
   of values (e.g. a second thickness variant), not a continuation.

Groups are capped at ``MAX_GROUP`` rows. Cells are joined with a space, except
after a trailing "-" followed by a lowercase letter ("Nitrogen-" + "containing")
or after a trailing "/" ("90° C./" + "90 sec").
"""

from __future__ import annotations

import re

MAX_GROUP = 6
CONNECTIVES = {"by", "of", "and", "or", "to", "parts", "per", "the", "a", "with", "in", "for"}
_VALUE = re.compile(
    r"^[<>~≈≤≥]?\s*-?\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?\s*"
    r"(?:%|nm|µm|um|mm|mJ/cm2|uC/cm2|°\s*C\.?|sec|s|min|h|parts?|wt%|kV)?$"
)
_DASHES = {"-", "—", "–", "‐", "―"}


def is_complete_value(cell: str) -> bool:
    c = cell.strip()
    return c in _DASHES or bool(_VALUE.match(c))


def is_unfinished(cell: str) -> bool:
    c = cell.strip()
    if not c:
        return False
    if c.count("(") > c.count(")"):
        return True
    if c[-1] in "-=/,(" and c not in _DASHES:
        return True
    # case-sensitive: "parts by" is unfinished, "Resin A" is a name
    return re.split(r"\s+", c)[-1] in CONNECTIVES


def _pad(row: list[str], width: int) -> list[str]:
    return row + [""] * (width - len(row))


def _continues(group: list[list[str]], merged: list[str], row: list[str]) -> bool:
    # a shorter row is padded (Google Patents omits trailing empty cells); a longer row
    # never continues a shorter one
    if len(row) > len(merged) or len(group) >= MAX_GROUP:
        return False
    row = _pad(row, len(merged))
    if any(is_unfinished(c) for c in merged):
        return True
    if row and not row[0].strip():
        for up, low in zip(merged, row, strict=True):
            if up.strip() and low.strip() and is_complete_value(up) and is_complete_value(low):
                return False
        return True
    return False


def join_cell(upper: str, lower: str) -> str:
    u, lo = upper.strip(), lower.strip()
    if not u:
        return lo
    if not lo:
        return u
    if u.endswith("/") or (u.endswith("-") and lo[:1].islower()):
        return u + lo
    return f"{u} {lo}"


def merge_cells(rows: list[list[str]]) -> list[str]:
    merged = list(rows[0])
    for row in rows[1:]:
        merged = [join_cell(u, lo) for u, lo in zip(merged, _pad(row, len(merged)), strict=True)]
    return merged


def group_wrapped_rows(rows: list[list[str]]) -> list[tuple[int, int]]:
    """Inclusive (start, end) index ranges of physical rows forming one logical row.

    Only groups of two or more rows are returned.
    """
    groups: list[tuple[int, int]] = []
    i = 0
    while i < len(rows):
        j = i
        merged = list(rows[i])
        while j + 1 < len(rows) and _continues(rows[i : j + 1], merged, rows[j + 1]):
            j += 1
            merged = merge_cells([merged, rows[j]])
        if j > i:
            groups.append((i, j))
        i = j + 1
    return groups
