"""Load the reconciled gold set and normalize it into tidy, typed tables.

Rules follow vocab.yaml v3: values are kept as printed in the raw columns and converted to
canonical units in new columns; doses are never converted across families.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .paths import GOLD_XLSX

LENGTH_TO_NM = {"nm": 1.0, "µm": 1e3, "um": 1e3, "μm": 1e3, "Å": 0.1, "mm": 1e6}
TIME_TO_S = {"s": 1.0, "sec": 1.0, "min": 60.0, "h": 3600.0, "hr": 3600.0}
DOSE_FAMILY = {"mJ/cm2": "photon", "uC/cm2": "electron", "mJ": "photon"}

POSITIVE_WORDS = {"good", "excellent", "○", "did not occur", "rectangular", "not generated", "superior"}
NEGATIVE_WORDS = {"poor", "bad", "×", "large", "taper", "peeling defects", "deformed", "decreased",
                  "increased", "too large", "impossible", "no resolution", "poorer", "na"}


@dataclass
class GoldSet:
    documents: pd.DataFrame
    records: pd.DataFrame
    components: pd.DataFrame
    results: pd.DataFrame
    reconciliation: pd.DataFrame
    qc: pd.DataFrame
    summary: pd.DataFrame
    readme: pd.DataFrame
    issues: list[dict] = field(default_factory=list)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _s(x) -> str:
    return x if isinstance(x, str) else ""


def exposure_family(row: pd.Series) -> str:
    src = _s(row.get("exposure_source"))
    tool = _s(row.get("exposure_tool")).lower()
    if src == "EUV_13.5":
        return "EUV"
    if src == "ebeam":
        return "e-beam"
    if "x-ray" in tool:
        return "X-ray"
    if "visible" in tool or "halide" in tool:
        return "visible"
    if src == "other" or row.get("dose_unit") in ("mJ/cm2", "mJ"):
        return "UV"
    return "none (coating only)"


def qualitative_class(text) -> str | None:
    """Map a qualitative result to 'positive' / 'negative' / None using the source's wording."""
    if not isinstance(text, str) or not text.strip():
        return None
    t = text.strip().lower()
    if any(w in t for w in ("not generated", "did not occur", "no cissing", "no residue")):
        return "positive"
    if t in {"na"} or any(w in t for w in NEGATIVE_WORDS - {"na"}):
        return "negative"
    if any(w in t for w in POSITIVE_WORDS):
        return "positive"
    return None


def _parse_ratio_amount(raw: str) -> tuple[float, dict[str, float]] | None:
    """'10 parts total; PAG3:PAG4 = 95:5' -> (10, {'PAG3': 0.95, 'PAG4': 0.05})."""
    m = re.match(r"\s*([\d.]+)\s*parts?\s*total;\s*([\w-]+):([\w-]+)\s*=\s*([\d.]+):([\d.]+)", raw or "")
    if not m:
        return None
    total, a, b, ra, rb = m.groups()
    ra, rb = float(ra), float(rb)
    return float(total), {a: ra / (ra + rb), b: rb / (ra + rb)}


def _normalize_components(comp: pd.DataFrame) -> pd.DataFrame:
    comp = comp.copy()
    comp["component_no"] = _num(comp["component_no"]).astype("Int64")
    comp["amount"] = _num(comp["amount_raw"])
    comp["is_balance"] = comp["amount_raw"].fillna("").str.contains("residual", case=False)
    # split printed mixture totals into the named components
    for idx, raw in comp["amount_raw"].items():
        parsed = _parse_ratio_amount(raw) if isinstance(raw, str) else None
        if parsed:
            total, shares = parsed
            name = comp.at[idx, "name_as_written"]
            share = next((v for k, v in shares.items() if k == name), None)
            if share is not None:
                comp.at[idx, "amount"] = total * share
    comp["name"] = comp["name_as_written"].fillna("").str.strip()
    # parts per hundred resin (phr): only where every component of the record shares a mass-like basis
    mass_like = {"parts_per_100_resin", "mass_g", "parts_by_mass"}
    phr = pd.Series(np.nan, index=comp.index)
    for rid, g in comp.groupby("record_id"):
        resin = g.loc[g["role"] == "resin", "amount"].sum(min_count=1)
        if not np.isfinite(resin) or resin <= 0:
            continue
        ok = g["amount_basis"].isin(mass_like) | g["amount"].isna()
        if not ok.all():
            continue
        phr.loc[g.index] = 100.0 * g["amount"] / resin
    comp["amount_phr"] = phr
    return comp


def _normalize_results(res: pd.DataFrame, issues: list[dict]) -> pd.DataFrame:
    res = res.copy()
    res["value_num"] = _num(res["value"])
    res["unit_canonical"] = res["unit"]
    is_length_metric = res["metric"].str.contains("_nm", na=False)
    scale = res["unit"].map(LENGTH_TO_NM)
    convert = is_length_metric & scale.notna() & (scale != 1.0)
    if convert.any():
        issues.append({
            "severity": "medium", "sheet": "Results", "kind": "unit_mislabel",
            "detail": f"{int(convert.sum())} values stored under *_nm metrics with unit "
                      f"{sorted(res.loc[convert, 'unit'].unique())}; converted to nm.",
            "records": sorted(res.loc[convert, "record_id"].str.split("_").str[0].unique()),
        })
    res.loc[convert, "value_num"] = res.loc[convert, "value_num"] * scale[convert]
    res.loc[convert, "unit_canonical"] = "nm"
    text = res["value_qualitative"].where(res["value_qualitative"].notna(), res["value"])
    res["outcome_class"] = [qualitative_class(t) if pd.isna(v) else None
                            for t, v in zip(text, res["value_num"])]
    res["sigma_num"] = _num(res["sigma"])
    res["pitch_nm"] = _num(res["pitch_nm"])
    return res


def _normalize_records(rec: pd.DataFrame, issues: list[dict]) -> pd.DataFrame:
    rec = rec.copy()
    rec["is_comparative"] = rec["is_comparative"].astype(str).str.lower().isin({"1", "true"})
    for col in ["solids_content_wt_pct", "softbake_temp", "peb_temp", "hardbake_temp", "dose",
                "ebeam_kv", "exposure_time_s", "intensity_mw_cm2", "developer_concentration"]:
        rec[col + "_num"] = _num(rec[col])
    rec["film_thickness_nm"] = _num(rec["film_thickness"]) * rec["film_thickness_unit"].map(LENGTH_TO_NM)
    for base in ["softbake", "peb", "developer", "hardbake"]:
        rec[f"{base}_time_s"] = _num(rec[f"{base}_time"]) * rec[f"{base}_time_unit"].map(TIME_TO_S)
    rec["exposure_family"] = rec.apply(exposure_family, axis=1)
    rec["dose_family"] = rec["dose_unit"].map(DOSE_FAMILY)
    bad_dose = rec["dose_unit"] == "mJ"
    if bad_dose.any():
        issues.append({
            "severity": "low", "sheet": "Records", "kind": "dose_unit_missing_area",
            "detail": f"{int(bad_dose.sum())} records have dose_unit='mJ' (no area); treated as mJ/cm2.",
            "records": sorted(rec.loc[bad_dose, "doc_id"].unique()),
        })
    empty = [c for c in ["dose_type", "intensity_mw_cm2"] if rec[c].isna().all()]
    if empty:
        issues.append({"severity": "low", "sheet": "Records", "kind": "empty_fields",
                       "detail": f"Fields never populated: {empty}.", "records": []})
    return rec


def _count_checks(g: GoldSet) -> list[dict]:
    actual = {"records": len(g.records), "components": len(g.components), "results": len(g.results),
              "reconciliation": len(g.reconciliation)}
    claimed_readme = {}
    if g.readme.shape[1] < 2 or g.summary.empty or "doc_id" not in g.summary:
        return []
    for key, value in zip(g.readme.iloc[:, 0].map(_s), g.readme.iloc[:, 1].map(_s)):
        m = re.search(r"([\d,]+)", value)
        for name, label in [("records", "Total Records"), ("components", "Total Components"),
                            ("results", "Total Results"), ("reconciliation", "Discrepancies")]:
            if key.startswith(label) and m:
                claimed_readme[name] = int(m.group(1).replace(",", ""))
    total = g.summary[g.summary["doc_id"].astype(str).str.startswith("TOTAL")]
    claimed_summary = {}
    if len(total):
        t = total.iloc[0]
        claimed_summary = {"records": int(t["Records"]), "components": int(t["Components"]),
                           "results": int(t["Results"]), "reconciliation": int(t["Reconciliation_Items"])}
    out = []
    for k, v in actual.items():
        a, b = claimed_readme.get(k), claimed_summary.get(k)
        if (a is not None and a != v) or (b is not None and b != v):
            out.append({"severity": "low", "sheet": "README/Summary", "kind": "count_mismatch",
                        "detail": f"{k}: actual rows {v}, README says {a}, Summary total says {b}.",
                        "records": []})
    return out


REQUIRED_SHEETS = ("Documents", "Records", "Components", "Results")
OPTIONAL_SHEETS = ("Reconciliation", "QC_and_Issues", "Summary", "README")


@lru_cache(maxsize=4)
def load_gold(path: str | Path = GOLD_XLSX) -> GoldSet:
    x = pd.read_excel(path, sheet_name=None, dtype=str)
    missing = [s for s in REQUIRED_SHEETS if s not in x]
    if missing:
        raise ValueError(f"workbook is missing required sheets: {missing}")
    for s in OPTIONAL_SHEETS:
        x.setdefault(s, pd.DataFrame(columns=["record_id", "doc_id", "cause"] if s != "README" else ["key", "value"]))
    issues: list[dict] = []
    docs = x["Documents"].copy()
    docs["year"] = _num(docs["year"]).astype("Int64")
    docs["records"] = _num(docs["records"]).astype("Int64")
    g = GoldSet(
        documents=docs,
        records=_normalize_records(x["Records"], issues),
        components=_normalize_components(x["Components"]),
        results=_normalize_results(x["Results"], issues),
        reconciliation=x["Reconciliation"].copy(),
        qc=x["QC_and_Issues"].copy(),
        summary=x["Summary"].copy(),
        readme=x["README"].copy(),
        issues=issues,
    )
    unparsed = g.components["amount"].isna() & g.components["amount_raw"].notna() & ~g.components["is_balance"]
    if unparsed.any():
        issues.append({"severity": "low", "sheet": "Components", "kind": "amount_unparsed",
                       "detail": f"{int(unparsed.sum())} amount strings could not be parsed: "
                                 f"{sorted(g.components.loc[unparsed, 'amount_raw'].unique())[:5]}",
                       "records": []})
    issues.extend(_count_checks(g))
    g.records = g.records.merge(docs[["doc_id", "year"]], on="doc_id", how="left")
    return g


def wide_results(g: GoldSet, doc_id: str) -> pd.DataFrame:
    """One row per record, one column per metric_as_written (numeric canonical values)."""
    ids = g.records.loc[g.records["doc_id"] == doc_id, "record_id"]
    r = g.results[g.results["record_id"].isin(ids)]
    return r.pivot_table(index="record_id", columns="metric_as_written", values="value_num",
                         aggfunc="first").reindex(ids)


def dataset_stats(g: GoldSet) -> dict:
    res = g.results
    varying = []
    for (doc, metric), grp in res.merge(g.records[["record_id", "doc_id"]], on="record_id").groupby(
            ["doc_id", "metric_as_written"]):
        vals = grp["value_num"].dropna()
        cls = grp["outcome_class"].dropna()
        varying.append({"doc_id": doc, "metric": metric, "n_numeric": len(vals),
                        "n_unique": vals.nunique(), "n_qual": len(cls), "n_qual_classes": cls.nunique()})
    v = pd.DataFrame(varying)
    informative = v[(v["n_unique"] > 1) | (v["n_qual_classes"] > 1)]
    return {
        "n_docs": g.documents["doc_id"].nunique(),
        "n_records": len(g.records),
        "n_comparative": int(g.records["is_comparative"].sum()),
        "n_components": len(g.components),
        "n_results": len(g.results),
        "n_metric_series": len(v),
        "n_informative_series": len(informative),
        "metric_series": v,
    }
