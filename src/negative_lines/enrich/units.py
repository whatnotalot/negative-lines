"""Unit conversion using the vocab.yaml tables. Dose is never converted."""

from __future__ import annotations

from negative_lines.vocab import get_vocab


def _convert(value: float | None, unit: str | None, table: dict[str, float]) -> float | None:
    if value is None or unit is None:
        return None
    if unit not in table:
        raise ValueError(f"unit {unit!r} not in vocab.yaml (accepted: {sorted(table)})")
    return round(value * table[unit], 9)


def to_nm(value: float | None, unit: str | None) -> float | None:
    return _convert(value, unit, get_vocab().length_units)


def to_seconds(value: float | None, unit: str | None) -> float | None:
    return _convert(value, unit, get_vocab().time_units)
