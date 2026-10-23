"""Record IDs: ``<doc_id>_<example slug>[_<variant slug>]`` (vocab: record_id).

PROVISIONAL convention (open team decision, must match the gold-set labelers):
``Example 3`` -> ``ex3``, ``Comparative Example 1`` -> ``cex1``,
``Reference Example 2`` -> ``rex2``; anything else is slugified (``W1`` -> ``w1``).
"""

from __future__ import annotations

import re

_PATTERNS = (
    (re.compile(r"^comparative\s+examples?\s*([0-9a-z][0-9a-z\-]*)$"), "cex"),
    (re.compile(r"^reference\s+examples?\s*([0-9a-z][0-9a-z\-]*)$"), "rex"),
    (re.compile(r"^(?:working\s+)?examples?\s*([0-9a-z][0-9a-z\-]*)$"), "ex"),
)


def slugify(text: str) -> str:
    s = re.sub(r"[^0-9a-z]+", "-", text.lower()).strip("-")
    return s or "x"


def example_slug(label: str) -> str:
    norm = re.sub(r"\s+", " ", label.strip().lower().replace(".", " ")).strip()
    norm = re.sub(r"\bno\b\s*", "", norm).strip()  # "Example No. 3"
    for pattern, prefix in _PATTERNS:
        m = pattern.match(norm)
        if m:
            return prefix + m.group(1).replace("-", "")
    return slugify(label)


def make_record_id(doc_id: str, example_label: str, variant_label: str | None = None) -> str:
    rid = f"{doc_id}_{example_slug(example_label)}"
    if variant_label:
        rid += f"_{slugify(variant_label)}"
    return rid


def unique_id(rid: str, taken: set[str]) -> str:
    """Append ``_2``, ``_3``... if ``rid`` is already used; records it as taken."""
    out, n = rid, 2
    while out in taken:
        out, n = f"{rid}_{n}", n + 1
    taken.add(out)
    return out
