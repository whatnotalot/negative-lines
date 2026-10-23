"""Dict builders for LLM-shaped payloads (what a provider would return as JSON)."""

from __future__ import annotations

REF = {"block_id": "p-0045", "location": "[0045]", "quote": "PAG-2 3 parts", "purpose": "value"}


def ref(block_id: str, location: str, quote: str, purpose: str = "value") -> dict:
    return {"block_id": block_id, "location": location, "quote": quote, "purpose": purpose}


def component(**kw) -> dict:
    base = {
        "role": "pag",
        "role_other_text": None,
        "name_as_written": "PAG-2",
        "definition_location": None,
        "polymer": None,
        "amount_value": 3.0,
        "amount_text": None,
        "amount_unit": "parts",
        "amount_basis": "parts_per_100_resin",
        "nonvolatile_content_pct": None,
        "mixture_id": None,
        "mixture_ratio": None,
        "confidence": "high",
        "note": None,
        "refs": [REF],
    }
    return base | kw


def result(**kw) -> dict:
    base = {
        "metric": "dose_gel",
        "metric_as_written": "gel dose Dg",
        "definition_as_written": None,
        "value": 12.0,
        "value_qualitative": None,
        "scale": None,
        "unit": "mJ/cm2",
        "sigma": None,
        "threshold_pct": None,
        "pitch_value": None,
        "pitch_unit": None,
        "pattern_type": None,
        "film_thickness": None,
        "film_thickness_unit": None,
        "position": None,
        "condition": None,
        "method": None,
        "reference_example_label": None,
        "figure_only": False,
        "confidence": "high",
        "note": None,
        "refs": [REF],
    }
    return base | kw


def exposure(**kw) -> dict:
    base = {
        "source": "i-line_365",
        "mode": "contact",
        "tool": None,
        "immersion": None,
        "dose": 100.0,
        "dose_unit": "mJ/cm2",
        "dose_type": None,
        "dose_meter_wavelength_nm": None,
        "wavelength_min_nm": None,
        "intensity_mw_cm2": None,
        "exposure_time": None,
        "exposure_time_unit": None,
        "ebeam_kv": None,
        "ion_species": None,
        "ion_energy_kev": None,
        "refs": [REF],
    }
    return base | kw


def bake(**kw) -> dict:
    base = {
        "temp_value": 95.0,
        "temp_text": None,
        "time": 2.0,
        "time_unit": "min",
        "method": None,
        "refs": [REF],
    }
    return base | kw


def development(**kw) -> dict:
    base = {
        "developer_name": "TMAH",
        "concentration": "2.38 wt%",
        "time": 60.0,
        "time_unit": "s",
        "temp_value": None,
        "temp_text": "RT",
        "method": "immersion",
        "rinse": "pure water",
        "refs": [REF],
    }
    return base | kw


def coating(**kw) -> dict:
    base = {
        "substrate": "silicon wafer",
        "primer": "HMDS",
        "underlayer": None,
        "coating_method": "spin coating",
        "film_thickness": 1.0,
        "film_thickness_unit": "um",
        "thickness_stage": "as_coated",
        "refs": [REF],
    }
    return base | kw


def record(**kw) -> dict:
    base = {
        "example_label": "Example 1",
        "variant_label": None,
        "is_comparative": False,
        "coating_only": False,
        "solids_content_wt_pct": None,
        "source_conflict_note": None,
        "components": [
            component(role="resin", name_as_written="Resin A", amount_value=100.0),
            component(),
        ],
        "process": {
            "coating": None,
            "softbake": {
                "steps": [
                    {"temp_value": 65.0, "temp_text": None, "time": 1.0, "time_unit": "min"},
                    {"temp_value": 95.0, "temp_text": None, "time": 3.0, "time_unit": "min"},
                ],
                "method": "hot_plate",
                "refs": [REF],
            },
            "exposure": exposure(),
            "peb": None,
            "development": None,
            "hardbake": None,
        },
        "results": [result()],
        "confidence": "high",
        "note": None,
        "refs": [REF],
    }
    return base | kw


def with_exposure(**kw) -> dict:
    rec = record()
    rec["process"]["exposure"] = exposure(**kw)
    return rec


def document_map(examples: list[tuple[str, bool]], doc_id: str = "SYNTH-0001A") -> dict:
    return {
        "document": {
            "source_type": "patent",
            "doc_id": doc_id,
            "title": "Negative-tone photosensitive resin composition",
            "assignee_or_authors": "Example Chemical Co., Ltd.",
            "year": 2021,
            "language": "en",
        },
        "examples": [
            {
                "label": label,
                "is_comparative": comp,
                "block_ids": [],
                "table_ids": ["t-1"],
                "has_results": True,
                "note": None,
            }
            for label, comp in examples
        ],
        "tables": [
            {
                "table_id": "t-1",
                "caption": "Table 1",
                "content": "composition",
                "examples_covered": [label for label, _ in examples],
            }
        ],
        "codename_definitions": [],
        "shared_conditions": [],
        "grade_scales": [],
        "note": None,
    }
