"""Targeted extraction rules, each tagged with its basis.

``basis``:

- ``vocab``: follows directly from a definition or note in ``vocab.yaml``
- ``guide``: follows from ``docs/hand-labeling-guide.md``
- ``schema``: follows from the structured-output schema / reference contract
- ``assumption``: a reasonable convention that the TEAM STILL HAS TO CONFIRM; listed in
  README ("Extraction rules awaiting team confirmation"). Change or remove freely.

The prompt is built from this list (``prompts.py``), so the rules and their status live
in one place. Each rule also names the observed failure it addresses, if any.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Basis = Literal["vocab", "guide", "schema", "assumption"]


@dataclass(frozen=True)
class Rule:
    id: str
    topic: str
    text: str
    basis: Basis
    source: str
    addresses: str = ""


RULES: tuple[Rule, ...] = (
    # ----- component roles -------------------------------------------------
    Rule(
        "role-pag",
        "roles",
        "A photoacid generator ('acid generator', sulfonium/iodonium salt, oxime sulfonate, "
        "codes such as PAG1) has role 'pag'. Use 'acid_amplifier' only if the source calls it "
        "an acid amplifier / acid proliferator (it is decomposed by acid and is not photoactive).",
        "vocab",
        "vocab.yaml roles.pag (synonym 'acid generator'), roles.acid_amplifier",
        "PAG1 extracted as acid_amplifier",
    ),  # fmt: skip
    Rule(
        "role-quencher",
        "roles",
        "A base that limits acid diffusion ('base', 'basic compound', 'acid diffusion control "
        "agent', amines such as trioctylamine) has role 'quencher', not 'additive'.",
        "vocab",
        "vocab.yaml roles.quencher synonyms; guide 'Components and roles' (trioctylamine)",
        "trioctylamine extracted as additive",
    ),  # fmt: skip
    Rule(
        "role-nitrogen-compound",
        "roles",
        "A component class named 'nitrogen-containing (organic) compound' in the source is a "
        "quencher.",
        "assumption",
        "common Japanese-patent convention; not a vocab synonym",
        "trioctylamine extracted as additive",
    ),  # fmt: skip
    Rule(
        "role-from-header",
        "roles",
        "When a table header names the component class of a column (e.g. '(B) Acid generator', "
        "'(C) Crosslinking agent'), use it to choose the role of every ingredient in that column.",
        "guide",
        "guide 'Assign the role the source gives the ingredient'",
    ),  # fmt: skip
    Rule(
        "role-carboxylic-acid",
        "roles",
        "An organic carboxylic acid added as a minor component (e.g. salicylic acid) is "
        "'additive' unless the source assigns another role.",
        "assumption",
        "matches gold v0 labels; no vocab role",
    ),  # fmt: skip
    # ----- amounts -------------------------------------------------------------
    Rule(
        "basis-phr",
        "amounts",
        "'parts by weight/mass' where the resin is 100 parts is 'parts_per_100_resin'. Use "
        "'parts_by_mass' only when the resin is not normalized to 100 parts.",
        "vocab",
        "vocab.yaml amount_bases.parts_per_100_resin / parts_by_mass definitions",
        "parts by weight with resin 100 extracted as parts_by_mass",
    ),  # fmt: skip
    Rule(
        "solvent-mixture",
        "amounts",
        "A mixed solvent ('PM/PE = 3/7', 'PGMEA/PGME 7/3') is one component per solvent: "
        "name each solvent separately, amount_value = its ratio number (3 and 7), "
        "amount_basis 'solvent_mass_ratio' if the source says the ratio is by mass, otherwise "
        "'solvent_ratio_unspecified'.",
        "vocab",
        "vocab.yaml roles.solvent ('mixed solvents = one component per solvent'), "
        "amount_bases.solvent_mass_ratio / solvent_ratio_unspecified",
        "'PM/PE = 3/7' extracted as one component without amounts",
    ),  # fmt: skip
    Rule(
        "solvent-codename",
        "amounts",
        "Solvent codenames are kept as written (PM, PE); give their definition location.",
        "guide",
        "guide golden rule 4 'Names as written'",
    ),  # fmt: skip
    # ----- process -------------------------------------------------------------
    Rule(
        "exposure-source",
        "process",
        "Choose the exposure source from the radiation actually used: electron beam / e-beam "
        "writer -> 'ebeam' (record ebeam_kv if stated); EUV or 13.5 nm -> 'EUV_13.5'; KrF/248 "
        "nm, ArF/193 nm, i-line/365 nm, g-line, h-line accordingly; several mercury lines -> "
        "'mixed_lines'; X-ray -> 'other'. Never infer EUV from fine resolution.",
        "vocab",
        "vocab.yaml exposure_sources (ebeam note: 'ebeam_kv required if stated')",
        "e-beam writer extracted as EUV_13.5 / other, kV lost",
    ),  # fmt: skip
    Rule(
        "exposure-mode-writer",
        "process",
        "An electron-beam writer means exposure mode 'ebeam_direct_write'.",
        "assumption",
        "vocab has the mode but no mapping rule",
        "mode left 'unspecified'",
    ),  # fmt: skip
    Rule(
        "peb-not-exposure",
        "process",
        "A temperature and time after exposure belong to the post-exposure bake (peb), not to "
        "the exposure.",
        "guide",
        "guide 'Process conditions' (PEB)",
        "PEB sentence cited for exposure",
    ),  # fmt: skip
    Rule(
        "film-vs-underlayer",
        "process",
        "process.coating.film_thickness is the thickness of the RESIST film. An underlayer or "
        "base film thickness goes into 'underlayer' (as text with material, bake and thickness).",
        "vocab",
        "vocab.yaml record.process.underlayer note",
        "underlayer thickness 420 nm extracted as resist film thickness",
    ),  # fmt: skip
    Rule(
        "no-invented-steps",
        "process",
        "Do not add process steps that are not stated (e.g. 'dried' is not a second softbake "
        "step at RT).",
        "guide",
        "guide golden rule 3 'Don't fill gaps from knowledge'",
        "invented softbake step 'RT'",
    ),  # fmt: skip
    Rule(
        "post-development-drying",
        "process",
        "'Dried with heating at X °C for Y s' after development/rinse is the hard bake.",
        "assumption",
        "matches gold v0 labels",
        "hard bake missing",
    ),  # fmt: skip
    # ----- context and inheritance ------------------------------------------
    Rule(
        "inherited-conditions",
        "context",
        "Section D (inherited procedure) supplies process steps only where sections A-C do not "
        "state their own value; cite such blocks with purpose 'inherited_condition'. Never take "
        "film thicknesses, solids contents, amounts or results from section D: they belong to "
        "the other example.",
        "assumption",
        "how 'the same method as Example N' is read; confirm with team",
        "solids content and results copied from Example 1",
    ),  # fmt: skip
    Rule(
        "table-row-wins",
        "context",
        "If the target example's table row and inherited text disagree, use the table row for "
        "the target example and mention the difference in source_conflict_note.",
        "assumption",
        "team rule X-1 in gold QC sheet ('resolved using Table 2')",
    ),  # fmt: skip
    # ----- record boundaries -------------------------------------------------
    Rule(
        "variants",
        "records",
        "One record = one formulation processed one way. If the target example reports the same "
        "formulation under several distinct experimental conditions (several film thicknesses "
        "such as '100/200', doses, bake temperatures, substrates or developers) and the results "
        "are given for each condition (or stated to hold for each), create one record per "
        "condition, set variant_label (e.g. 'film 100 nm'), and give each record its own "
        "condition value. Otherwise create one record.",
        "guide",
        "guide 'Record boundaries' ('Same formulation exposed at 3 doses ... three "
        "records'); generalized to other conditions",
        "100/200 nm variants not split",
    ),  # fmt: skip
    Rule(
        "results-context",
        "results",
        "Give each result the pattern_type (L/S -> 'line_space', isolated line -> "
        "'isolated_line') and the film_thickness it refers to. A statement such as 'thickness "
        "loss did not occur in Examples 1 to 24' is a result of the target example "
        "(value_qualitative).",
        "vocab",
        "vocab.yaml results.pattern_type, results.film_thickness; metrics.thickness_loss",
        "pattern type, thickness and thickness-loss result missing",
    ),  # fmt: skip
    # ----- quotes ------------------------------------------------------------
    Rule(
        "verbatim-quotes",
        "quotes",
        "Each quote is copied character for character from the ONE block whose ID you cite "
        "(at most 200 characters; you may shorten by cutting, never by rewording). Do not combine "
        "text from several blocks into one quote; cite several refs instead. For a table cell, "
        "quote the cell text as shown in that row.",
        "schema",
        "SourceRef.quote / block_id descriptions; guide golden rule 5",
        "paraphrased quotes and quotes attributed to the wrong block",
    ),  # fmt: skip
)


def rules_text(basis_filter: tuple[Basis, ...] | None = None) -> str:
    lines = []
    for topic in dict.fromkeys(r.topic for r in RULES):
        items = [
            r
            for r in RULES
            if r.topic == topic and (basis_filter is None or r.basis in basis_filter)
        ]
        if not items:
            continue
        lines.append(f"{topic.upper()}:")
        lines += [f"- {r.text}" for r in items]
    return "\n".join(lines)


def assumptions() -> list[Rule]:
    return [r for r in RULES if r.basis == "assumption"]
