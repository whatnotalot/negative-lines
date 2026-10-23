"""Explicit field mapping between vocab.yaml, the LLM schemas and the full record.

Paths use the flattened notation of ``Vocab.record_fields``:
``components[].polymer.mw``, ``process.exposure.dose``.

LLM-side targets are prefixed with the model they live in:
``record:`` = ``LLMRecord`` (per example) and ``document:`` = ``DocumentInfo``
(from the document map). A vocab path not listed in ``VOCAB_TO_LLM`` maps to
the same path under ``record:``.

``tests/test_vocab_consistency.py`` checks this file in both directions, so
any new vocab field must be mapped, excluded or added here deliberately.
"""

from __future__ import annotations

#: vocab paths the LLM never produces, with the reason.
LLM_EXCLUDED: dict[str, str] = {
    "record_id": "built by code: <doc_id>_<example label>[_<variant>]",
    "provenance.extraction_model": "pipeline metadata",
    "provenance.confidence": "computed from LLM confidence and quote verification",
    "provenance.human_verified": "set by reviewers",
    "components[].name_resolved": "computed",
    "components[].smiles": "computed",
    "components[].cas": "computed",
    "components[].pubchem_cid": "computed",
    "components[].amount_wt_pct_solids": "computed",
    "process.exposure.dose_computed": "computed",
    "compliance.flags[].component_ref": "compliance agent",
    "compliance.flags[].rule": "compliance agent",
    "compliance.flags[].list_version_date": "compliance agent",
    "compliance.flags[].rationale": "compliance agent",
}

#: vocab path -> LLM path(s) where names or structure differ.
VOCAB_TO_LLM: dict[str, tuple[str, ...]] = {
    # provenance comes from the document map, the rest from the record
    "provenance.source_type": ("document:source_type",),
    "provenance.doc_id": ("document:doc_id",),
    "provenance.title": ("document:title",),
    "provenance.assignee_or_authors": ("document:assignee_or_authors",),
    "provenance.year": ("document:year",),
    "provenance.location": ("record:refs",),
    "provenance.evidence_snippet": ("record:refs",),
    "provenance.is_comparative": ("record:is_comparative",),
    "provenance.labeler_confidence": ("record:confidence",),
    "provenance.labeler_note": ("record:note",),
    # components: number-or-text split
    "components[].amount_raw": (
        "record:components[].amount_value",
        "record:components[].amount_text",
    ),
    "components[].labeler_confidence": ("record:components[].confidence",),
    "components[].labeler_note": ("record:components[].note",),
    # process: flat in vocab, grouped (with refs per group) in the LLM schema
    "process.substrate": ("record:process.coating.substrate",),
    "process.primer": ("record:process.coating.primer",),
    "process.underlayer": ("record:process.coating.underlayer",),
    "process.coating_method": ("record:process.coating.coating_method",),
    "process.film_thickness": ("record:process.coating.film_thickness",),
    "process.film_thickness_unit": ("record:process.coating.film_thickness_unit",),
    "process.thickness_stage": ("record:process.coating.thickness_stage",),
    "process.softbake_steps[].temp": (
        "record:process.softbake.steps[].temp_value",
        "record:process.softbake.steps[].temp_text",
    ),
    "process.softbake_steps[].time": ("record:process.softbake.steps[].time",),
    "process.softbake_steps[].time_unit": ("record:process.softbake.steps[].time_unit",),
    "process.bake_method": (
        "record:process.softbake.method",
        "record:process.peb.method",
        "record:process.hardbake.method",
    ),
    "process.exposure.exposure_time_s": (
        "record:process.exposure.exposure_time",
        "record:process.exposure.exposure_time_unit",
    ),
    "process.peb_temp": ("record:process.peb.temp_value", "record:process.peb.temp_text"),
    "process.peb_time": ("record:process.peb.time",),
    "process.peb_time_unit": ("record:process.peb.time_unit",),
    "process.developer.name": ("record:process.development.developer_name",),
    "process.developer.concentration": ("record:process.development.concentration",),
    "process.developer.time": ("record:process.development.time",),
    "process.developer.time_unit": ("record:process.development.time_unit",),
    "process.developer.temp": (
        "record:process.development.temp_value",
        "record:process.development.temp_text",
    ),
    "process.developer.method": ("record:process.development.method",),
    "process.rinse": ("record:process.development.rinse",),
    "process.hardbake_temp": (
        "record:process.hardbake.temp_value",
        "record:process.hardbake.temp_text",
    ),
    "process.hardbake_time": ("record:process.hardbake.time",),
    "process.hardbake_time_unit": ("record:process.hardbake.time_unit",),
    # results
    "results[].pitch_nm": ("record:results[].pitch_value", "record:results[].pitch_unit"),
    "results[].reference_record_id": ("record:results[].reference_example_label",),
    "results[].labeler_confidence": ("record:results[].confidence",),
    "results[].labeler_note": ("record:results[].note",),
}

#: LLM paths that have no vocab counterpart (source references and extraction aids).
LLM_EXTENSIONS: frozenset[str] = frozenset(
    {
        "document:language",
        "record:example_label",
        "record:variant_label",
        "record:components[].refs",
        "record:process.coating.refs",
        "record:process.softbake.refs",
        "record:process.exposure.refs",
        "record:process.peb.refs",
        "record:process.development.refs",
        "record:process.hardbake.refs",
        "record:results[].film_thickness_unit",
        "record:results[].figure_only",
        "record:results[].refs",
    }
)

#: Record (``FormulationRecord``) paths that vocab.yaml does not define.
RECORD_EXTENSIONS: frozenset[str] = frozenset(
    {
        "provenance.refs",
        "components[].refs",
        "process.refs",
        "results[].figure_only",
        "results[].refs",
        "vocab_version",
        "warnings",
    }
)


def llm_targets(vocab_path: str) -> tuple[str, ...]:
    """LLM paths that hold the information for a vocab path (empty if excluded)."""
    if vocab_path in LLM_EXCLUDED:
        return ()
    return VOCAB_TO_LLM.get(vocab_path, (f"record:{vocab_path}",))
