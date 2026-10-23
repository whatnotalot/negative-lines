"""Parse example references in patent text: "Examples 3, 5 and 7", "Examples 1 to 24",
"Comparative Example 1", "Synthesis Example 2", "Example 1-2".

A reference is a key ``(kind, number)``:

- ``ex``  : Example / Working Example / Embodiment
- ``cex`` : Comparative Example
- ``rex`` : Reference Example
- ``syn`` : Synthesis / Preparation / Production / Polymerization Example (ingredient
  preparation, not a formulation)

Numbers are kept as text so sub-numbered examples ("1-2", as in "Example 1-2") stay
atomic (a hyphen is never read as a range); "to" / "through" / "~" ranges are expanded
between plain integers ("1 to 24") and between sub-numbers with the same prefix
("1-1 to 1-6").
"""

from __future__ import annotations

import re

Key = tuple[str, str]

_KIND = {
    None: "ex",
    "comparative": "cex",
    "reference": "rex",
    "synthesis": "syn",
    "synthetic": "syn",
    "preparation": "syn",
    "production": "syn",
    "polymerization": "syn",
}
_NUM = r"\d+(?:-\d+)?[A-Za-z]?"
_SEP = r"\s*(?:,|and|or|to|through|~|-)\s*"
REF = re.compile(
    rf"\b(?:(?P<kind>comparative|reference|synthesis|synthetic|preparation|production|"
    rf"polymerization)\s+)?(?:working\s+)?(?:examples?|embodiments?)\s+(?:no\.?\s*)?"
    rf"(?P<list>{_NUM}(?:{_SEP}{_NUM})*)",
    re.IGNORECASE,
)
_RANGE_WORD = re.compile(r"\s*(?:to|through|~)\s*", re.I)


def _expand(listing: str) -> list[str]:
    # tokens and separators, e.g. "3, 5 and 7" / "1 to 24" / "1-1 to 1-6"
    parts = re.split(r"(\s*(?:,|and|or|to|through|~)\s*)", listing, flags=re.I)
    nums: list[str] = []
    pending_range = False
    for p in parts:
        if not p.strip():
            continue
        if re.fullmatch(_SEP, p, flags=re.I) or p.strip(", ").lower() in {"and", "or"}:
            pending_range = bool(_RANGE_WORD.fullmatch(p))
            continue
        n = p.strip()
        prev = nums[-1] if nums else ""
        sub_prev, sub_n = re.fullmatch(r"(\d+)-(\d+)", prev), re.fullmatch(r"(\d+)-(\d+)", n)
        if pending_range and prev.isdigit() and n.isdigit() and int(n) >= int(prev):
            nums.extend(str(i) for i in range(int(prev) + 1, int(n) + 1))
        elif (pending_range and sub_prev and sub_n and sub_prev.group(1) == sub_n.group(1)
              and int(sub_n.group(2)) >= int(sub_prev.group(2))):  # fmt: skip
            head = sub_prev.group(1)
            nums.extend(
                f"{head}-{i}" for i in range(int(sub_prev.group(2)) + 1, int(sub_n.group(2)) + 1)
            )
        else:
            nums.append(n)
        pending_range = False
    return nums


def find_refs(text: str) -> list[tuple[Key, int, int]]:
    """All example references with their character span."""
    out = []
    for m in REF.finditer(text):
        kind = _KIND[(m.group("kind") or "").lower() or None]
        for n in _expand(m.group("list")):
            out.append(((kind, n.lower()), m.start(), m.end()))
    return out


def keys_in(text: str) -> set[Key]:
    return {k for k, _, _ in find_refs(text)}


def label_key(label: str) -> Key | None:
    """Key of an example label from the document map ('Example 3', 'Comparative Example 1')."""
    refs = find_refs(label)
    return refs[0][0] if refs else None


def is_example_key(key: Key) -> bool:
    return key[0] in ("ex", "cex", "rex")


def heading_keys(heading: str) -> set[Key]:
    """Keys of a heading that *starts* with an example reference (e.g. 'Examples 3 to 24 and
    Comparative Example 1'); empty for sub-headings such as 'Two-Layer Resist Method'."""
    m = REF.match(heading.strip())
    return keys_in(heading) if m else set()
