"""Optimization campaigns: one patent's example table turned into a typed design space.

Each campaign holds the observed records (factors + objectives + provenance), an encoder to the
unit hypercube, factor groups for additive kernels, and a candidate grid for prospective design.
"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable

import numpy as np
import pandas as pd

from .compliance import DefaultScreener, ScreenResult
from .data import GoldSet, load_gold
from .rls import z_factor


@dataclass
class Factor:
    name: str
    kind: str                                 # "cat" | "cont"
    label: str
    levels: list | None = None                # cat levels
    bounds: tuple[float, float] | None = None # cont bounds
    family: dict | None = None                # cat level -> family (adds hierarchical one-hot)

    @property
    def families(self) -> list:
        return sorted(set(self.family.values())) if self.family else []

    @property
    def width(self) -> int:
        return len(self.levels) + len(self.families) if self.kind == "cat" else 1


@dataclass
class Objective:
    key: str
    label: str
    unit: str
    log: bool = True          # model log(y)
    direction: str = "min"


@dataclass
class Campaign:
    key: str
    title: str
    doc_id: str
    exposure: str
    blurb: str
    factors: list[Factor]
    objectives: list[Objective]
    scalar: Objective                          # single-objective target used for EI replay
    table: pd.DataFrame                        # one row per experiment
    grid: dict[str, list]                      # candidate values per factor
    yvar_cols: dict[str, str] = field(default_factory=dict)
    constant_components: list[dict] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    components_fn: Callable | None = None     # row -> components; overrides the per-key registry

    # ---- encoding -------------------------------------------------------------------------
    def encode(self, df: pd.DataFrame) -> np.ndarray:
        cols = []
        for f in self.factors:
            v = df[f.name]
            if f.kind == "cat":
                cols.append(np.stack([(v == lvl).to_numpy(float) for lvl in f.levels], 1))
                if f.family:
                    fam = v.map(f.family)
                    cols.append(np.stack([(fam == fm).to_numpy(float) for fm in f.families], 1))
            else:
                lo, hi = f.bounds
                cols.append(((v.to_numpy(float) - lo) / (hi - lo if hi > lo else 1.0))[:, None])
        return np.concatenate(cols, 1)

    def groups(self) -> list[list[int]]:
        out, i = [], 0
        for f in self.factors:
            out.append(list(range(i, i + f.width)))
            i += f.width
        return out

    def cont_dims(self) -> list[int]:
        return [g[0] for f, g in zip(self.factors, self.groups()) if f.kind == "cont"]

    # ---- data access ----------------------------------------------------------------------
    @property
    def observed(self) -> pd.DataFrame:
        return self.table[~self.table["failed"]]

    def y(self, key: str, df: pd.DataFrame | None = None) -> np.ndarray:
        df = self.observed if df is None else df
        return df[key].to_numpy(float)

    def objective(self, key: str) -> Objective:
        return next(o for o in [*self.objectives, self.scalar] if o.key == key)

    # ---- candidates -----------------------------------------------------------------------
    def candidates(self, max_n: int = 20000, seed: int = 0) -> pd.DataFrame:
        names = list(self.grid)
        sizes = [len(self.grid[n]) for n in names]
        if int(np.prod(sizes, dtype=float)) <= max_n:
            rows = list(itertools.product(*[self.grid[n] for n in names]))
        else:  # uniform random subset of the full factorial
            rng = np.random.default_rng(seed)
            idx = {tuple(int(rng.integers(s)) for s in sizes) for _ in range(max_n)}
            rows = [tuple(self.grid[n][i] for n, i in zip(names, t)) for t in sorted(idx)]
        cand = pd.DataFrame(rows, columns=names)
        return self.derive(cand)

    def derive(self, df: pd.DataFrame) -> pd.DataFrame:
        """Hook for derived factor columns (overridden via _DERIVE)."""
        fn = _DERIVE.get(self.key)
        return fn(df) if fn else df

    def components_of(self, row: pd.Series) -> list[dict]:
        fn = self.components_fn or _COMPONENTS.get(self.key)
        comps = fn(row) if fn else []
        return comps + self.constant_components

    def screen(self, df: pd.DataFrame, swaps: dict[str, str] | None = None, screener=None) -> list[ScreenResult]:
        screener = screener or DefaultScreener()
        out = []
        for _, row in df.iterrows():
            comps = self.components_of(row)
            if swaps:
                comps = [{**c, "name": swaps.get(c["name"], c["name"])} for c in comps]
            out.append(screener.screen(comps, self.doc_id))
        return out


_DERIVE: dict = {}
_COMPONENTS: dict = {}


def _code(name: str) -> str:
    return re.sub(r"[()]", "", name or "").strip()


def _metric(g: GoldSet, ids, metric: str, written_contains: str | None = None) -> pd.Series:
    r = g.results[g.results["record_id"].isin(ids) & (g.results["metric"] == metric)]
    if written_contains:
        r = r[r["metric_as_written"].str.contains(written_contains, case=False, na=False, regex=False)]
    return r.groupby("record_id")["value_num"].first()


def _provenance(g: GoldSet, ids) -> pd.DataFrame:
    rec = g.records.set_index("record_id").loc[ids]
    return rec[["example_label", "is_comparative", "location", "evidence_snippet", "labeler_confidence"]]


# ================================================================================================
# EUV: Tokyo Ohka Kogyo US20230314945A1
# ================================================================================================
def _euv(g: GoldSet) -> Campaign:
    doc = "US20230314945A1"
    ids = g.records.loc[g.records["doc_id"] == doc, "record_id"].tolist()
    comp = g.components[g.components["record_id"].isin(ids)]
    first = lambda role: comp[comp["role"] == role].groupby("record_id")["name"].first().map(_code)
    amt = lambda role: comp[comp["role"] == role].groupby("record_id")["amount"].first()
    dev = g.records.set_index("record_id").loc[ids, "developer_name"].fillna("")
    t = pd.DataFrame(index=pd.Index(ids, name="record_id"))
    t["resin"], t["pag"], t["crosslinker"], t["quencher"] = first("resin"), first("pag"), first("crosslinker"), first("quencher")
    t["crosslinker_phr"] = amt("crosslinker")
    t["developer"] = np.where(dev.str.contains("TMAH"), "TMAH (aq)", "butyl acetate")
    t["Eop"] = _metric(g, ids, "sensitivity_esize")
    t["LWR"] = _metric(g, ids, "lwr_3sigma_nm")
    t["HP"] = 16.0
    t["Z"] = z_factor(t["HP"], t["LWR"], t["Eop"])
    t["failed"] = t["Eop"].isna()
    t = t.join(_provenance(g, ids)).reset_index()
    levels = lambda col, pre, n: [f"{pre}-{i}" for i in range(1, n + 1)]
    factors = [
        Factor("resin", "cat", "Resin", levels("resin", "A", 7)),
        Factor("pag", "cat", "PAG", levels("pag", "B", 7)),
        Factor("crosslinker", "cat", "Crosslinker", levels("crosslinker", "C", 3)),
        Factor("crosslinker_phr", "cont", "Crosslinker (phr)", bounds=(10.0, 30.0)),
        Factor("quencher", "cat", "Quencher", levels("quencher", "D", 5)),
        Factor("developer", "cat", "Developer", ["TMAH (aq)", "butyl acetate"]),
    ]
    grid = {f.name: (f.levels if f.kind == "cat" else [10.0, 20.0, 30.0]) for f in factors}
    return Campaign(
        key="euv", title="EUV 13.5 nm: TOK negative-tone resist", doc_id=doc, exposure="EUV",
        blurb="19 examples varying one component at a time (PAG, crosslinker, quencher, resin) on a "
              "16 nm L/S pattern at NA 0.33. Objectives: dose to size (Eop) and LWR.",
        factors=factors,
        objectives=[Objective("Eop", "Eop", "mJ/cm²"), Objective("LWR", "LWR", "nm")],
        scalar=Objective("Z", "Z-factor", "×10⁻⁸ mJ·nm³"),
        table=t, grid=grid,
        constant_components=[{"role": "additive", "name": "(E)-1: salicylic acid"},
                             {"role": "solvent", "name": "PGME/PGMEA"}],
        caveats=["Resolution is fixed at 16 nm for every resolved example, so Z uses HP = 16 nm.",
                 "Comparative Example 1 (resin A-7) did not resolve: kept as a failed experiment.",
                 "Example 17 changes developer, crosslinker loading and solvent at once (confounded)."],
    )


def _euv_components(row) -> list[dict]:
    return [{"role": "resin", "name": f"({row['resin']})"}, {"role": "pag", "name": f"({row['pag']})"},
            {"role": "crosslinker", "name": f"({row['crosslinker']})"},
            {"role": "quencher", "name": f"({row['quencher']})"}]


_COMPONENTS["euv"] = _euv_components


# ================================================================================================
# E-beam: FUJIFILM US7432034B2 (50 kV e-beam subset)
# ================================================================================================
PAG_FAMILY_RE = re.compile(r"^(PAG\d|III|II|I|J)")


def _pag_family(code: str) -> str:
    m = PAG_FAMILY_RE.match(code)
    return m.group(1) if m else code


def _xl_family(code: str) -> str:
    return code.split("-")[0]


def _ebeam(g: GoldSet) -> Campaign:
    doc = "US7432034B2"
    rec = g.records[(g.records["doc_id"] == doc) & (g.records["exposure_family"] == "e-beam")]
    ids = rec["record_id"].tolist()
    comp = g.components[g.components["record_id"].isin(ids)].copy()
    resin_g = comp[comp["role"] == "resin"].groupby("record_id")["amount"].sum()
    comp["phr"] = 100 * comp["amount"] / comp["record_id"].map(resin_g)
    t = pd.DataFrame(index=pd.Index(ids, name="record_id"))
    xl = comp[comp["role"] == "crosslinker"].copy()
    xl["fam"] = xl["name"].map(_xl_family)
    for fam in ["MM", "CL", "C"]:
        t[f"xl_{fam}_phr"] = xl[xl["fam"] == fam].groupby("record_id")["phr"].sum().reindex(ids).fillna(0.0)
    t["xl_families"] = xl.groupby("record_id")["fam"].nunique().reindex(ids).astype(float)
    pag = comp[comp["role"] == "pag"].groupby("record_id")
    t["pag"], t["pag_phr"] = pag["name"].first(), pag["phr"].sum()
    q = comp[comp["role"] == "quencher"].groupby("record_id")
    t["quencher"], t["quencher_phr"] = q["name"].first(), q["phr"].sum()
    t["resin"] = comp[comp["role"] == "resin"].groupby("record_id")["name"].first()
    t["LER"] = _metric(g, ids, "ler_3sigma_nm")
    t["sensitivity"] = _metric(g, ids, "sensitivity_esize")
    t["resolution"] = _metric(g, ids, "resolution_min_cd_nm")
    t["Z"] = z_factor(t["resolution"], t["LER"], t["sensitivity"])
    t["failed"] = t["LER"].isna()
    t = t.join(_provenance(g, ids)).reset_index()
    pags = sorted(t["pag"].unique(), key=lambda s: (_pag_family(s), s))
    quenchers = sorted(t["quencher"].unique())
    factors = [
        Factor("xl_MM_phr", "cont", "MM-type crosslinker (phr)", bounds=(0.0, 36.0)),
        Factor("xl_CL_phr", "cont", "CL-type crosslinker (phr)", bounds=(0.0, 36.0)),
        Factor("xl_C_phr", "cont", "C-type crosslinker (phr)", bounds=(0.0, 36.0)),
        Factor("xl_families", "cont", "Crosslinker families mixed", bounds=(1.0, 2.0)),
        Factor("pag", "cat", "PAG (code within family)", pags, family={p: _pag_family(p) for p in pags}),
        Factor("pag_phr", "cont", "PAG (phr)", bounds=(5.0, 15.0)),
        Factor("quencher", "cat", "Quencher", quenchers),
        Factor("quencher_phr", "cont", "Quencher (phr)", bounds=(0.2, 0.8)),
    ]
    grid = {
        "xl_MM_phr": [0.0, 7.0, 14.0, 21.0, 28.0], "xl_CL_phr": [0.0, 7.0, 14.0, 21.0, 28.0],
        "xl_C_phr": [0.0, 7.0], "pag": pags, "pag_phr": [8.0, 10.0, 12.0],
        "quencher": quenchers, "quencher_phr": [0.3, 0.45, 0.6],
    }
    return Campaign(
        key="ebeam", title="E-beam 50 kV: FUJIFILM negative resist", doc_id=doc, exposure="e-beam",
        blurb="14 e-beam examples. The invention mixes two crosslinker families (MM-x + CL-x); the "
              "single-family comparatives show 2-3x worse LER. Objectives: LER, sensitivity, resolution.",
        factors=factors,
        objectives=[Objective("LER", "LER", "nm"), Objective("sensitivity", "Sensitivity", "µC/cm²"),
                    Objective("resolution", "Resolution", "nm")],
        scalar=Objective("Z", "Z-factor (e-beam)", "×10⁻⁸ µC·nm³"),
        table=t, grid=grid,
        constant_components=[{"role": "surfactant", "name": 'Megafac F176 ("W-1")'},
                             {"role": "solvent", "name": "propylene glycol monomethyl ether acetate"}],
        caveats=["13 different resins are used, mostly once each: resin identity is not modeled.",
                 "X-ray examples (mJ/cm²) are excluded: doses are never compared across families.",
                 "Every formulation contains Megafac F176, a fluorosurfactant."],
    )


def _ebeam_derive(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    xl = df[["xl_MM_phr", "xl_CL_phr", "xl_C_phr"]]
    df["xl_families"] = (xl > 0).sum(1).clip(1, 2).astype(float)
    total = xl.sum(1)
    return df[(total >= 20) & (total <= 42) & ((xl > 0).sum(1) <= 2)].reset_index(drop=True)


def _ebeam_components(row) -> list[dict]:
    comps = [{"role": "pag", "name": row["pag"]}, {"role": "quencher", "name": row["quencher"]}]
    for fam in ["MM", "CL", "C"]:
        if row.get(f"xl_{fam}_phr", 0) > 0:
            comps.append({"role": "crosslinker", "name": f"{fam}-x"})
    return comps


_DERIVE["ebeam"] = _ebeam_derive
_COMPONENTS["ebeam"] = _ebeam_components


# ================================================================================================
# SU-8 thick film: FormFactor US20070248896A1, Example 8 via cracking
# ================================================================================================
CRACK_RE = re.compile(r"ex8_crack_(mod|unmod)_(\d+)_(fast|slow)_w(\d)")


def _su8(g: GoldSet) -> Campaign:
    doc = "US20070248896A1"
    ids = [r for r in g.records.loc[g.records["doc_id"] == doc, "record_id"] if CRACK_RE.search(r)]
    res = g.results[g.results["record_id"].isin(ids) &
                    g.results["metric_as_written"].str.contains("via cracking", na=False)]
    rows = []
    for rid, grp in res.groupby("record_id"):
        vals = grp["value_num"].dropna().to_numpy()
        if len(vals) == 0:
            continue
        mod, dose, ramp, wafer = CRACK_RE.search(rid).groups()
        rows.append({"record_id": rid, "formulation": "modified" if mod == "mod" else "unmodified",
                     "dose": float(dose), "ramp": ramp, "wafer": int(wafer), "vals": vals})
    w = pd.DataFrame(rows)
    cond = []
    for (form, dose, ramp), grp in w.groupby(["formulation", "dose", "ramp"]):
        vals = np.concatenate(grp["vals"].to_list())
        cond.append({"record_id": " + ".join(grp["record_id"]), "formulation": form, "dose": dose,
                     "ramp": ramp, "cracking": vals.mean(),
                     "cracking_var": max(vals.var(ddof=1) / len(vals), 1.0), "n_readings": len(vals),
                     "wafer_values": "; ".join(f"w{r.wafer}: {', '.join(f'{v:g}' for v in r.vals)}"
                                               for r in grp.itertuples())})
    t = pd.DataFrame(cond)
    first = g.records.set_index("record_id").loc[[r.split(" + ")[0] for r in t["record_id"]]]
    t["example_label"] = [f"Ex. 8: {f}, {int(d)} mJ/cm², {r} ramp" for f, d, r in
                          zip(t["formulation"], t["dose"], t["ramp"])]
    t["is_comparative"] = t["formulation"] == "unmodified"
    t["location"] = first["location"].to_numpy()
    t["evidence_snippet"] = first["evidence_snippet"].to_numpy()
    t["labeler_confidence"] = first["labeler_confidence"].to_numpy()
    t["failed"] = False
    factors = [
        Factor("formulation", "cat", "Formulation", ["unmodified", "modified"]),
        Factor("dose", "cont", "Exposure dose (mJ/cm²)", bounds=(1200.0, 2310.0)),
        Factor("ramp", "cat", "Bake ramp", ["fast", "slow"]),
    ]
    grid = {"formulation": ["unmodified", "modified"], "dose": list(np.linspace(1200, 2310, 38)),
            "ramp": ["fast", "slow"]}
    return Campaign(
        key="su8", title="SU-8 thick film: FormFactor via cracking", doc_id=doc, exposure="UV",
        blurb="Example 8 crosses formulation (stock vs plasticized SU-8) x dose x bake ramp, two wafers "
              "each, four quadrant readings per wafer. Objective: % of vias cracked.",
        factors=factors,
        objectives=[Objective("cracking", "Via cracking", "%", log=False)],
        scalar=Objective("cracking", "Via cracking", "%", log=False),
        table=t, grid=grid, yvar_cols={"cracking": "cracking_var"},
        caveats=["Unmodified SU-8 at slow ramp was only reported at 2310 mJ/cm².",
                 "Noise per condition comes from the spread of the 8 quadrant readings."],
    )


def _su8_components(row) -> list[dict]:
    if row["formulation"] == "modified":
        return [{"role": "resin", "name": "Epon SU-8 resin"}, {"role": "pag", "name": "Cyracure 6974"},
                {"role": "additive", "name": "dioctyl phthalate (DOP)"},
                {"role": "adhesion_promoter", "name": "glycidoxypropane-trimethoxysilane (GPTMS)"}]
    return [{"role": "resin", "name": "unmodified SU-8 masking composition"}]


_COMPONENTS["su8"] = _su8_components

BUILDERS = {"euv": _euv, "ebeam": _ebeam, "su8": _su8}


@lru_cache(maxsize=8)
def get_campaign(key: str) -> Campaign:
    return BUILDERS[key](load_gold())


def all_campaigns() -> dict[str, Campaign]:
    return {k: get_campaign(k) for k in BUILDERS}
