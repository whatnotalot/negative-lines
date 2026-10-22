"""Compliance screening adapter used as a constraint by the design loop.

This is a screening aid, not legal advice. The authoritative screen belongs to the team's
compliance agent: anything that implements ``Screener.screen`` can replace ``DefaultScreener``.

Knowledge comes from three places, each recorded on the flag it produces:
  * the extraction team's QC sheet (PFAS PAG findings read from patent structures),
  * product-family identity (e.g. Megaface F-series fluorosurfactants), which must be verified on SDS,
  * SMILES substructure rules (OECD 2021 PFAS definition) when a structure is available.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Protocol

SEVERITY_ORDER = {"block": 3, "penalize": 2, "watch": 1, "clear": 0}
PENALTY = {"block": 1.0, "penalize": 0.5, "watch": 0.1, "clear": 0.0}


@dataclass(frozen=True)
class Flag:
    component: str
    rule: str          # OECD_PFAS | REACH_SVHC | REACH_AnnexXVII | metal | none
    severity: str      # block | penalize | watch | clear
    rationale: str
    source: str        # extraction_qc | product_family | smiles_rule | name_rule
    confidence: str    # high | medium | low
    substitutes: tuple[str, ...] = ()


@dataclass
class ScreenResult:
    flags: list[Flag] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)

    @property
    def worst(self) -> str:
        return max((f.severity for f in self.flags), key=SEVERITY_ORDER.get, default="clear")

    @property
    def penalty(self) -> float:
        return max((PENALTY[f.severity] for f in self.flags), default=0.0)

    @property
    def pfas(self) -> bool:
        return any(f.rule == "OECD_PFAS" and f.severity == "block" for f in self.flags)

    def summary(self) -> str:
        if not self.flags and not self.unverified:
            return "clear"
        parts = [f"{f.severity.upper()} {f.rule}: {f.component}" for f in self.flags if f.severity != "clear"]
        if self.unverified:
            parts.append(f"unverified structure: {', '.join(self.unverified)}")
        return "; ".join(parts) or "clear"


class Screener(Protocol):
    def screen(self, components: Iterable[dict], doc_id: str | None = None) -> ScreenResult: ...


# --- knowledge table ---------------------------------------------------------------------------
# (doc_id or None for any document, role or None, name regex, Flag template fields)
_PFAS_PAG_SUBS = ("camphorsulfonate onium salt", "arenesulfonate (e.g. tosylate) onium salt",
                  "non-fluorinated bulky alkylsulfonate", "metal-oxo (e.g. tin-oxo) resist platform")

KNOWLEDGE: list[tuple[str | None, str | None, str, dict]] = [
    # extraction team QC sheet (PFAS_REGULATORY_RESTRICTION rows)
    ("US20080241753A1", "pag", r"^PAG1$", dict(rule="OECD_PFAS", severity="block", confidence="high",
        source="extraction_qc", rationale="Triflate (CF3SO3-) anion per QC sheet.", substitutes=_PFAS_PAG_SUBS)),
    ("US20080241753A1", "pag", r"^PAG2$", dict(rule="OECD_PFAS", severity="block", confidence="high",
        source="extraction_qc", rationale="Nonaflate (C4F9SO3-) anion per QC sheet.", substitutes=_PFAS_PAG_SUBS)),
    ("US7432034B2", "pag", r"^(I-1|PAG4-36)$", dict(rule="OECD_PFAS", severity="block", confidence="high",
        source="extraction_qc", rationale="Perfluorobutanesulfonate (C4F9SO3-) anion per QC sheet.",
        substitutes=_PFAS_PAG_SUBS)),
    ("US20230314945A1", "pag", r"^\(B-[1-7]\)$", dict(rule="OECD_PFAS", severity="block", confidence="high",
        source="extraction_qc", rationale="All EUV PAGs B-1..B-7 carry fluorinated anions per QC sheet.",
        substitutes=_PFAS_PAG_SUBS)),
    # inorganic fluoroanion PAGs: not PFAS under OECD (no fully fluorinated carbon)
    (None, "pag", r"cyracure\s*(uvi-)?6974", dict(rule="metal", severity="watch", confidence="medium",
        source="product_family", rationale="Triarylsulfonium SbF6- salt: not PFAS (no CF2/CF3) but an "
        "antimony compound; check hazard classification.", substitutes=("triarylsulfonium PF6- salt",))),
    (None, "pag", r"cyracure\s*uvi-6990", dict(rule="none", severity="clear", confidence="medium",
        source="product_family", rationale="Triarylsulfonium PF6- salt: inorganic fluoroanion, not PFAS under OECD 2021.")),
    (None, "sensitizer", r"hexafluoroantimonate", dict(rule="metal", severity="watch", confidence="high",
        source="name_rule", rationale="Contains SbF6- (antimony); not PFAS under OECD 2021.")),
    # surfactants
    (None, "surfactant", r"(megaf|^f-?\d{3}|^r-?08|\br08\b)", dict(rule="OECD_PFAS", severity="block",
        confidence="medium", source="product_family", rationale="Megaface F-/R-series are fluorinated "
        "surfactants (perfluoroalkyl groups); verify on SDS.", substitutes=("BYK-3xx polyether-modified PDMS",))),
    (None, "surfactant", r"^fc-\d+", dict(rule="OECD_PFAS", severity="block", confidence="medium",
        source="product_family", rationale="Fluorad FC-series are fluorochemical surfactants; verify on SDS.",
        substitutes=("BYK-3xx polyether-modified PDMS",))),
    (None, "surfactant", r"^byk", dict(rule="none", severity="clear", confidence="medium",
        source="product_family", rationale="BYK-3xx are polyether-modified polydimethylsiloxanes (no fluorine).")),
    (None, "surfactant", r"polydimethylsiloxane", dict(rule="none", severity="clear", confidence="high",
        source="name_rule", rationale="Silicone leveling agent (no fluorine).")),
    # plasticizer / solvents
    (None, "additive", r"dioctyl phthalate|\bdop\b", dict(rule="REACH_SVHC", severity="penalize",
        confidence="medium", source="name_rule", rationale="'DOP' usually denotes DEHP (REACH SVHC, Annex XIV); "
        "if di-n-octyl phthalate, still a restricted phthalate. Confirm CAS.",
        substitutes=("DINCH", "acetyl tributyl citrate (ATBC)", "DEHT/DOTP"))),
    ("WO2004107052A1", "solvent", r"^MCA$", dict(rule="REACH_SVHC", severity="watch", confidence="low",
        source="name_rule", rationale="Abbreviation undefined in source; if 2-methoxyethyl acetate it is a "
        "REACH SVHC (reprotoxic). Confirm identity.", substitutes=("PGMEA",))),
]

FLUORO_NAME = re.compile(r"(perfluoro|trifluoromethane|triflate|nonaflate|fluoroalkyl|C\dF\d)", re.I)
PATENT_CODE = re.compile(r"^\(?[A-Z]{1,4}\d?[- ]?\d{0,3}\)?(-\d+)?$|^PAG ?\d|^(Resin|Polymer|Amine) ?\(?\d", re.I)
STRUCTURE_ROLES = {"pag", "quencher", "crosslinker", "acid_amplifier", "photoinitiator", "sensitizer"}


def oecd_pfas_smiles(smiles: str) -> bool | None:
    """True if the structure has a fully fluorinated methyl/methylene carbon (OECD 2021)."""
    try:
        from rdkit import Chem
    except ImportError:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    patt = Chem.MolFromSmarts("[CX4;!$([CX4][#1,Cl,Br,I])](F)F")
    mol = Chem.AddHs(mol)
    return mol.HasSubstructMatch(patt)


class DefaultScreener:
    """Rule-based screen over component dicts with keys: role, name (and optionally smiles)."""

    def screen_component(self, comp: dict, doc_id: str | None = None) -> tuple[list[Flag], bool]:
        name = (comp.get("name") or "").strip()
        role = comp.get("role")
        flags = []
        for kdoc, krole, pattern, tmpl in KNOWLEDGE:
            if kdoc and kdoc != doc_id:
                continue
            if krole and krole != role:
                continue
            if re.search(pattern, name, re.I):
                flags.append(Flag(component=name, **tmpl))
        smiles = comp.get("smiles")
        if smiles and not any(f.rule == "OECD_PFAS" for f in flags):
            hit = oecd_pfas_smiles(smiles)
            if hit:
                flags.append(Flag(name, "OECD_PFAS", "block", "SMILES contains a CF2/CF3 carbon "
                                  "(OECD 2021 definition).", "smiles_rule", "high", _PFAS_PAG_SUBS))
        if not flags and FLUORO_NAME.search(name):
            flags.append(Flag(name, "OECD_PFAS", "block", "Name indicates a perfluoroalkyl group.",
                              "name_rule", "medium", _PFAS_PAG_SUBS))
        unverified = (not flags and not smiles and role in STRUCTURE_ROLES and bool(PATENT_CODE.search(name)))
        return flags, unverified

    def screen(self, components: Iterable[dict], doc_id: str | None = None) -> ScreenResult:
        out = ScreenResult()
        for comp in components:
            flags, unverified = self.screen_component(comp, doc_id)
            out.flags.extend(flags)
            if unverified:
                out.unverified.append(comp.get("name"))
        return out


RULE_COLUMNS = ["doc_id", "role", "name_pattern", "rule", "severity", "rationale", "source", "confidence",
                "substitutes"]


class TableScreener(DefaultScreener):
    """Rules from a table (e.g. the compliance agent's output), with the same columns as `rules_table()`.

    name_pattern is a case-insensitive regex matched against the component name; doc_id and role may be
    blank to match any. substitutes is a ';'-separated list. With replace_default=False the table's rules
    are checked first and the built-in rules still apply to components the table does not cover.
    """

    def __init__(self, table, replace_default: bool = False):
        import pandas as pd

        df = pd.read_csv(table) if not isinstance(table, pd.DataFrame) else table
        missing = {"name_pattern", "rule", "severity"} - set(df.columns)
        if missing:
            raise ValueError(f"compliance table is missing columns: {sorted(missing)}")
        bad = set(df["severity"]) - set(SEVERITY_ORDER)
        if bad:
            raise ValueError(f"unknown severities {sorted(bad)}; use one of {list(SEVERITY_ORDER)}")
        self.rules = []
        for r in df.fillna("").to_dict("records"):
            subs = tuple(s.strip() for s in str(r.get("substitutes", "")).split(";") if s.strip())
            self.rules.append((r.get("doc_id") or None, r.get("role") or None, str(r["name_pattern"]), dict(
                rule=r["rule"], severity=r["severity"], rationale=r.get("rationale", ""),
                source=r.get("source") or "compliance_agent", confidence=r.get("confidence") or "medium",
                substitutes=subs)))
        self.replace_default = replace_default

    def screen_component(self, comp: dict, doc_id: str | None = None):
        name, role = (comp.get("name") or "").strip(), comp.get("role")
        flags = [Flag(component=name, **tmpl) for kdoc, krole, pattern, tmpl in self.rules
                 if (not kdoc or kdoc == doc_id) and (not krole or krole == role) and re.search(pattern, name, re.I)]
        if flags or self.replace_default:
            return flags, False
        return super().screen_component(comp, doc_id)


def rules_table():
    """The built-in knowledge as a table: a template for the compliance agent's rules file."""
    import pandas as pd

    rows = [{"doc_id": d or "", "role": r or "", "name_pattern": p, **{k: v for k, v in t.items() if k != "substitutes"},
             "substitutes": "; ".join(t.get("substitutes", ()))} for d, r, p, t in KNOWLEDGE]
    return pd.DataFrame(rows, columns=RULE_COLUMNS)


def screen_records(components, records, screener: Screener | None = None):
    """Screen every record; returns a DataFrame indexed by record_id."""
    import pandas as pd

    screener = screener or DefaultScreener()
    doc_of = records.set_index("record_id")["doc_id"]
    rows = []
    for rid, grp in components.groupby("record_id"):
        res = screener.screen(grp[["role", "name"]].to_dict("records"), doc_of.get(rid))
        pag_names = set(grp.loc[grp["role"] == "pag", "name"])
        on_pag = [f for f in res.flags if f.component in pag_names]
        rows.append({
            "record_id": rid,
            "worst": res.worst,
            "penalty": res.penalty,
            "pfas": res.pfas,
            "pfas_pag": any(f.rule == "OECD_PFAS" and f.severity == "block" for f in on_pag),
            "pag_worst": max((f.severity for f in on_pag), key=SEVERITY_ORDER.get, default="clear"),
            "pag_unverified": bool(pag_names & set(res.unverified)),
            "summary": res.summary(),
            "n_flags": len(res.flags),
        })
    return pd.DataFrame(rows).set_index("record_id")


def flag_table(components, records, screener: Screener | None = None):
    """One row per (component name, doc) with its flags, for display."""
    import pandas as pd

    screener = screener or DefaultScreener()
    c = components.merge(records[["record_id", "doc_id"]], on="record_id")
    rows = []
    for (doc, role, name), grp in c.groupby(["doc_id", "role", "name"]):
        flags, unverified = screener.screen_component({"role": role, "name": name}, doc)
        for f in flags or [None]:
            rows.append({
                "doc_id": doc, "role": role, "component": name, "n_records": len(grp),
                "severity": f.severity if f else ("unverified" if unverified else "clear"),
                "rule": f.rule if f else "", "rationale": f.rationale if f else
                ("Patent-local code with no structure in the dataset." if unverified else ""),
                "source": f.source if f else "", "confidence": f.confidence if f else "",
                "substitutes": ", ".join(f.substitutes) if f else "",
            })
    return pd.DataFrame(rows)
