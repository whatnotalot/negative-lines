"""``amount_wt_pct_solids`` (computed field) from amounts as printed.

Rules (vocab ``amount_bases.*.convertible_to_wt_pct_solids`` and the guide's
worked example):

- Solids = every component except ``role: solvent``.
- All solid components must share one basis; mixed bases are not combined.
- ``wt_pct_solids``: copied as is.
- Other bases with ``convertible_to_wt_pct_solids: true`` (phr, parts_by_mass,
  mass_g, wt_pct_total) are mass-proportional: wt% = amount / sum(solids) x 100.
  ``nonvolatile_content_pct`` scales a solution-supplied resin to its solids.
- ``needs_molar_masses`` / ``needs_density`` / ``false`` bases: not computed.
- Every solid component needs a numeric amount; otherwise nothing is computed
  (a partial sum would silently inflate the others).
- Components sharing a ``mixture_id`` are not split: not computed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from negative_lines.vocab import get_vocab


class _Amount(Protocol):
    role: str
    name_as_written: str
    amount_value: float | None
    amount_basis: str | None
    nonvolatile_content_pct: float | None
    mixture_id: str | None


def compute_wt_pct_solids(components: Sequence[_Amount]) -> tuple[list[float | None], list[str]]:
    out: list[float | None] = [None] * len(components)
    solids = [i for i, c in enumerate(components) if c.role != "solvent"]
    with_amount = [i for i in solids if components[i].amount_value is not None]
    if not with_amount:
        return out, []

    if any(components[i].mixture_id for i in solids):
        return out, ["wt% of solids not computed: mixture amounts are not split per component"]

    bases = {components[i].amount_basis for i in solids}
    if bases == {"wt_pct_solids"}:
        for i in solids:
            out[i] = components[i].amount_value
        return out, []
    if len(bases) != 1:
        return out, [
            f"wt% of solids not computed: solid components use different bases {sorted(map(str, bases))}"
        ]

    (basis,) = bases
    convertible = get_vocab().raw["amount_bases"][basis]["convertible_to_wt_pct_solids"]
    if convertible is not True:
        return out, [f"wt% of solids not computed: basis {basis!r} is {convertible!s} in vocab"]

    missing = [components[i].name_as_written for i in solids if components[i].amount_value is None]
    if missing:
        return out, [f"wt% of solids not computed: no numeric amount for {missing}"]

    masses = {}
    for i in solids:
        c = components[i]
        m = float(c.amount_value)  # type: ignore[arg-type]
        if c.nonvolatile_content_pct is not None:
            m *= c.nonvolatile_content_pct / 100.0
        masses[i] = m
    total = sum(masses.values())
    if total <= 0:
        return out, ["wt% of solids not computed: solids sum to 0"]
    for i, m in masses.items():
        out[i] = round(m / total * 100.0, 6)
    return out, []
