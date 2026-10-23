"""Minimal gold v0 -> vocab v3 mapping.

Principles: originals are always preserved by the adapter; only unambiguous
differences are normalized; anything uncertain is flagged ``ambiguous`` and
left unchanged. Every decision returns a ``Flag`` so it can be reviewed in
the team's reconciliation meeting.

Metric rule (only applied when gold ``metric == "other"``): compare the head of
``metric_as_written`` (text before ``,``/``(``/``/``, casefolded) with the
v3 metric names and synonyms in vocab.yaml:

- strong match: head == synonym, head starts with "<synonym> ", or a non-ASCII
  synonym (e.g. Korean) occurs in the head. Exactly one metric -> normalized;
  several -> ambiguous (e.g. "peeling" is a synonym of both adhesion and peeling).
- weak match: a synonym starts with the head (e.g. "edge roughness" vs
  "edge roughness (CD loss)") -> ambiguous suggestion, unchanged.
- no match -> stays "other" (valid v3; e.g. "% via cracking", "wafer bow").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from negative_lines.vocab import get_vocab

FlagStatus = Literal["normalized", "ambiguous", "invalid", "rule_violation"]


@dataclass(frozen=True)
class Flag:
    field: str
    original: Any
    value: Any
    status: FlagStatus
    note: str


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().casefold())


@lru_cache(maxsize=1)
def _metric_synonyms() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, spec in get_vocab().raw["metrics"].items():
        if name == "other":
            continue
        syns = [name.replace("_", " "), *(spec.get("synonyms") or [])]
        out[name] = [_norm(s) for s in syns]
    return out


def metric_head(metric_as_written: str) -> str:
    return _norm(re.split(r"[,(/]", metric_as_written, maxsplit=1)[0])


def normalize_metric(metric: str, metric_as_written: str | None) -> tuple[str, Flag | None]:
    if metric != "other" or not metric_as_written:
        return metric, None
    head = metric_head(metric_as_written)
    if not head:
        return metric, None
    strong, weak = set(), set()
    for name, syns in _metric_synonyms().items():
        for s in syns:
            if head == s or head.startswith(s + " ") or (not s.isascii() and s in head):
                strong.add(name)
            elif s.startswith(head):
                weak.add(name)
    if len(strong) == 1:
        (new,) = strong
        return new, Flag("metric", metric, new, "normalized",
                         f"'{metric_as_written}' matches v3 metric {new!r}")  # fmt: skip
    if len(strong) > 1:
        return metric, Flag("metric", metric, None, "ambiguous",
                            f"'{metric_as_written}' matches several v3 metrics {sorted(strong)}")  # fmt: skip
    if weak:
        return metric, Flag("metric", metric, None, "ambiguous",
                            f"'{metric_as_written}' may be v3 metric {sorted(weak)} (partial match)")  # fmt: skip
    return metric, None


def normalize_exposure_source(
    source: str | None, tool: str | None
) -> tuple[str | None, Flag | None]:
    if source != "other" or not tool:
        return source, None
    t = _norm(tool)
    if "mixed line" in t or ("i-line" in t and "g-line" in t):
        return "mixed_lines", Flag("exposure_source", source, "mixed_lines", "normalized",
                                   "tool names several mercury lines")  # fmt: skip
    if "visible" in t:
        return "visible", Flag("exposure_source", source, "visible", "normalized",
                               "tool describes visible light")  # fmt: skip
    if "x-ray" in t:
        return source, None  # X-ray has no v3 source: 'other' is correct
    if re.search(r"\buv\b|ultraviolet|mercury|metal halide", t):
        return source, Flag("exposure_source", source, None, "ambiguous",
                            "UV tool without wavelength: maybe broadband_uv")  # fmt: skip
    return source, None


def normalize_dose_unit(unit: str | None) -> tuple[str | None, Flag | None]:
    if unit is None:
        return None, None
    allowed = get_vocab().dose_units
    if unit in allowed:
        return unit, None
    if unit == "mJ":
        return None, Flag("dose_unit", unit, None, "ambiguous",
                          "'mJ' is not a dose unit; probably mJ/cm2 (left unset)")  # fmt: skip
    return None, Flag(
        "dose_unit", unit, None, "invalid", f"not a vocab dose unit {sorted(allowed)}"
    )


_MIXTURE = re.compile(
    r"^\s*(?P<total>\d+(?:\.\d+)?)\s*parts?\s+total\s*;\s*(?P<names>[^=]+?)\s*=\s*(?P<ratio>[\d.:\s/]+)\s*$",
    re.I,
)


def parse_mixture(amount_raw: str) -> tuple[str, str] | None:
    """'10 parts total; PAG3:PAG4 = 95:5' -> (mixture_id 'PAG3+PAG4', ratio '95:5')."""
    m = _MIXTURE.match(amount_raw)
    if not m:
        return None
    names = "+".join(n.strip() for n in re.split(r"[:/]", m.group("names")))
    return names, m.group("ratio").strip()
