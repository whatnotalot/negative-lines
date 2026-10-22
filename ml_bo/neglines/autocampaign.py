"""Build a campaign automatically from any patent in the gold-set schema.

Factors are whatever varies across the patent's examples: the identity of the main component in each
role, each role's loading (phr when every amount is mass-based, raw amount otherwise) and numeric process
settings. Objectives are the best-covered numeric result series that vary. This lets newly extracted
patents flow into the surrogate and BO without hand-written campaign code; the curated campaigns in
campaigns.py remain the reference versions for the three patents they cover.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .campaigns import Campaign, Factor, Objective
from .data import GoldSet

PROCESS_FIELDS = {
    "dose_num": "Dose", "film_thickness_nm": "Film thickness (nm)", "softbake_temp_num": "Soft bake (°C)",
    "peb_temp_num": "PEB (°C)", "peb_time_s": "PEB time (s)", "developer_time_s": "Develop time (s)",
    "ebeam_kv_num": "E-beam (kV)", "hardbake_temp_num": "Hard bake (°C)", "exposure_time_s_num": "Exposure (s)",
}
MAXIMIZE_WORDS = ("shear", "adhesion", "hardness", "retention", "contrast", "aspect ratio", "selectivity")
PERFORMANCE_WORDS = ("roughness", "ler", "lwr", "resolution", "sensitivity", "eop", "crack", "u %", "uniform",
                     "defect", "bow", "adhesion", "shear", "etch", "contrast")
SETPOINT_WORDS = ("thickness", "viscosity")


def _priority(metric_as_written: str) -> int:
    m = metric_as_written.lower()
    if any(w in m for w in PERFORMANCE_WORDS):
        return 0
    return 2 if any(w in m for w in SETPOINT_WORDS) else 1


def _slug(text: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    return s[:40] or "objective"


def objective_direction(metric_as_written: str) -> str:
    return "max" if any(w in metric_as_written.lower() for w in MAXIMIZE_WORDS) else "min"


def objective_options(g: GoldSet, doc_id: str, min_coverage: float = 0.6) -> pd.DataFrame:
    """Numeric result series of one patent that vary, ranked by how many records report them."""
    ids = g.records.loc[g.records["doc_id"] == doc_id, "record_id"]
    r = g.results[g.results["record_id"].isin(ids) & g.results["value_num"].notna()]
    if r.empty:
        return pd.DataFrame(columns=["metric_as_written", "n", "n_unique", "unit", "direction"])
    out = r.groupby("metric_as_written").agg(n=("record_id", "nunique"), n_unique=("value_num", "nunique"),
                                             unit=("unit_canonical", "first")).reset_index()
    n_rec = r["record_id"].nunique()
    out = out[(out["n_unique"] > 1) & (out["n"] >= max(4, min_coverage * n_rec))]
    out["direction"] = out["metric_as_written"].map(objective_direction)
    out["priority"] = out["metric_as_written"].map(_priority)
    return out.sort_values(["priority", "n", "n_unique"], ascending=[True, False, False]).reset_index(drop=True)


def viability(g: GoldSet) -> pd.DataFrame:
    rows = []
    for doc in g.documents["doc_id"]:
        opts = objective_options(g, doc)
        try:
            c = build_auto_campaign(g, doc) if len(opts) else None
        except ValueError:
            c = None
        rows.append({"doc_id": doc, "objectives_available": len(opts),
                     "experiments": 0 if c is None else len(c.observed),
                     "factors": 0 if c is None else len(c.factors),
                     "viable": c is not None and len(c.observed) >= 5 and len(c.factors) >= 1})
    return pd.DataFrame(rows)


def build_auto_campaign(g: GoldSet, doc_id: str, objectives: list[str] | None = None,
                        max_objectives: int = 2, directions: dict[str, str] | None = None) -> Campaign:
    opts = objective_options(g, doc_id)
    if opts.empty:
        raise ValueError(f"{doc_id}: no numeric result varies across its examples")
    chosen = objectives or opts["metric_as_written"].head(max_objectives).tolist()
    ids = g.records.loc[g.records["doc_id"] == doc_id, "record_id"].tolist()
    res = g.results[g.results["record_id"].isin(ids)]
    wide = res.pivot_table(index="record_id", columns="metric_as_written", values="value_num", aggfunc="first")
    wide = wide.reindex(columns=chosen).dropna()
    if len(wide) < 3:
        raise ValueError(f"{doc_id}: fewer than 3 records report all of {chosen}")
    rids = wide.index.tolist()
    rec = g.records.set_index("record_id").loc[rids]
    comp = g.components[g.components["record_id"].isin(rids)].copy()

    t = pd.DataFrame(index=pd.Index(rids, name="record_id"))
    factors, cat_roles = [], []
    for role, grp in comp.groupby("role"):
        if role == "solvent" and grp["name"].nunique() <= 1:
            continue
        main = grp.sort_values("amount", ascending=False).groupby("record_id")["name"].first().reindex(rids)
        if main.nunique() > 1:
            t[role] = main.fillna("(none)")
            factors.append(Factor(role, "cat", role.replace("_", " ").title(), sorted(t[role].unique())))
            cat_roles.append(role)
        use_phr = grp["amount_phr"].notna().all()
        amt = grp.groupby("record_id")["amount_phr" if use_phr else "amount"].sum(min_count=1).reindex(rids)
        amt = amt.fillna(0.0)
        if amt.nunique() > 1 and role != "resin":
            col = f"{role}_amt"
            t[col] = amt
            unit = "phr" if use_phr else (grp["amount_unit"].dropna().iloc[0] if grp["amount_unit"].notna().any() else "")
            factors.append(Factor(col, "cont", f"{role.replace('_', ' ').title()} ({unit})".replace(" ()", ""),
                                  bounds=(float(amt.min()), float(amt.max()))))
    for col, label in PROCESS_FIELDS.items():
        if col in rec and rec[col].nunique(dropna=True) > 1:
            v = rec[col].astype(float)
            t[col] = v.fillna(v.median())
            factors.append(Factor(col, "cont", label, bounds=(float(v.min()), float(v.max()))))
    if not factors:
        raise ValueError(f"{doc_id}: nothing varies across the examples that report {chosen}")

    objs = []
    directions = directions or {}
    for m in chosen:
        key = _slug(m)
        t[key] = wide[m]
        unit = opts.set_index("metric_as_written")["unit"].get(m)
        unit = unit if isinstance(unit, str) else ""
        label = re.sub(r"\s*\((?:um|µm|μm|nm|uc/cm2|uC/cm2|mJ/cm2)\)", "", m, flags=re.I).strip()[:48]
        objs.append(Objective(key, label, unit, log=bool((wide[m] > 0).all()),
                              direction=directions.get(m, objective_direction(m))))
    t["failed"] = False
    t = t.join(rec[["example_label", "is_comparative", "location", "evidence_snippet", "labeler_confidence"]]).reset_index()

    # constant components (present in every record, never varying) are screened with every candidate
    counts = comp.groupby(["role", "name"])["record_id"].nunique()
    constant = [{"role": r, "name": n} for (r, n), k in counts.items() if k == len(rids) and r not in cat_roles]
    grid = {}
    for f in factors:
        grid[f.name] = f.levels if f.kind == "cat" else list(np.unique(np.round(np.linspace(*f.bounds, 4), 6)))
    key = f"auto:{doc_id}"

    def components_of(row, roles=tuple(cat_roles)):
        return [{"role": r, "name": row[r]} for r in roles if row.get(r) not in (None, "(none)")]

    exposure = rec["exposure_family"].mode().iloc[0]
    title = g.documents.set_index("doc_id").loc[doc_id, "applicant_or_inventor"]
    return Campaign(
        key=key, title=f"{doc_id} (auto): {title}", doc_id=doc_id, exposure=exposure,
        blurb=f"Auto-built from {len(t)} examples: {len(factors)} varying factors, objectives "
              f"{', '.join(o.label for o in objs)}.",
        factors=factors, objectives=objs, scalar=objs[0], table=t, grid=grid,
        constant_components=constant, components_fn=components_of,
        caveats=["Built automatically: check that the chosen objectives and directions make sense.",
                 "Only records that report every chosen objective are used."],
    )
