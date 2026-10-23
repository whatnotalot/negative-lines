"""Versioned prompts for the two extraction stages.

Bump ``PROMPT_VERSION`` whenever the wording changes: it is part of the cache key and is
recorded with every extraction run. Targeted rules live in ``extract/rules.py`` (each
tagged as vocab-/guide-grounded or as a team assumption).

Never put held-out gold-set documents in here (eval/split.yaml).

History:
- 2026-10-22.1  first version, whole document per example
- 2026-10-23.1  per-example context (sections A-F), targeted rules, variant rule
"""

from __future__ import annotations

import json

from negative_lines.extract.context import ExampleContext
from negative_lines.extract.rules import rules_text
from negative_lines.schema.llm import DocumentMap

PROMPT_VERSION = "2026-10-23.1"

BASE_RULES = """\
You extract negative photoresist formulation data from patents and papers into the given JSON schema.
The document is given as blocks, each prefixed with its ID in brackets, e.g. [p-0045] or [t-1-r-3].
A table row ID like [t-1-r-7-9] is one logical row that the source printed over several lines.

Rules (from the project labeling guide):
1. Copy, don't convert: amounts, doses, temperatures and times exactly as printed, with the printed unit.
2. Missing is null, never 0. Do not fill gaps from general knowledge.
3. Names as written, including codenames such as "PAG-2"; do not resolve them.
4. Every component, result and process group cites the most specific block (table row or paragraph)
   with a short verbatim quote. Cite additional blocks for codename definitions (purpose
   'codename_definition'), conditions stated once for several examples ('shared_condition'),
   conditions taken from an inherited procedure ('inherited_condition') and grade legends
   ('grade_scale').
5. When unsure, choose the best value, set confidence 'low' and explain in note.
Amounts: "wt% relative to / based on / per resin" is parts_per_100_resin. A bare "%" is 'unspecified'
(confidence low). Solution solids content goes to solids_content_wt_pct, not to a component.
Doses: never convert between mJ/cm2 and uC/cm2. If only intensity and time are given, leave dose null.
A sensitivity reported as a result (Eop, D50, gel dose) is a result metric, not the process dose.
Use the source's definition of a metric: a dose that prints the target size (Eop, Esize) is
sensitivity_esize; use sensitivity_unspecified only when no definition is given.
Qualitative grades: copy the symbol and the source's legend (scale). Room temperature is "RT".
Figures: never read values off plots; record figure-only evidence with value null and figure_only true.
Claims with ranges ("1-10 parts, preferably 3") are not formulations.
"""

SYSTEM = BASE_RULES + "\nTargeted rules:\n" + rules_text() + "\n"

CONTEXT_GUIDE = """\
The context below was assembled for the target example only:
A = its own section text, B = its table rows (with headers), C = other passages naming it:
    values here belong to the target example.
D = procedure of another example that the target explicitly refers to: use only for process steps
    that A-C do not state; never take thicknesses, solids contents, amounts or results from D.
E = definitions of ingredients and codenames. F = conditions or legends shared by several examples.
"""


def map_messages(document_text: str) -> list[tuple[str, str]]:
    return [
        ("system", SYSTEM),
        (
            "human",
            "Build the document map: list every worked example and comparative example that has "
            "concrete amounts, the tables, codename definitions, conditions shared by several "
            "examples, and grade legends.\n\n" + document_text,
        ),
    ]


def _map_summary(dmap: DocumentMap, example_label: str) -> str:
    summary = {
        "target_example": [e.model_dump() for e in dmap.examples if e.label == example_label],
        "codename_definitions": [c.model_dump() for c in dmap.codename_definitions],
        "shared_conditions": [s.model_dump() for s in dmap.shared_conditions],
        "grade_scales": [g.model_dump() for g in dmap.grade_scales],
    }
    return json.dumps(summary, ensure_ascii=False)


def example_messages(
    context_text: str, dmap: DocumentMap, example_label: str
) -> list[tuple[str, str]]:
    return [
        ("system", SYSTEM),
        (
            "human",
            f"Extract all records for the example labelled {example_label!r}.\n"
            "One record per formulation processed one way (see the 'variants' rule). Apply shared "
            "and inherited conditions that cover this example and cite them.\n\n"
            f"{CONTEXT_GUIDE}\n"
            f"Document map (from a previous step):\n{_map_summary(dmap, example_label)}\n\n"
            f"Context:\n{context_text}",
        ),
    ]


def example_messages_for(ctx: ExampleContext, doc, dmap: DocumentMap) -> list[tuple[str, str]]:
    return example_messages(ctx.render(doc), dmap, ctx.label)
