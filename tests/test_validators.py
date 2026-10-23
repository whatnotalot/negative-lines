"""Labeling-guide rules enforced by the LLM schema validators."""

from __future__ import annotations

import copy

import pytest
from builders import REF, component, exposure, record, result, with_exposure
from pydantic import ValidationError

from negative_lines.schema.llm import ExampleExtraction, LLMComponent, LLMRecord, LLMResult
from negative_lines.schema.record import Component, Exposure, FormulationRecord, Result

# ----- valid input ------------------------------------------------------


def test_valid_record_roundtrips_through_json():
    rec = LLMRecord.model_validate(record())
    again = LLMRecord.model_validate_json(rec.model_dump_json())
    assert again == rec
    assert rec.warnings() == []


def test_example_extraction_accepts_several_records():
    ex = ExampleExtraction.model_validate(
        {
            "example_label": "Example 1",
            "records": [record(), record(variant_label="dose 2")],
            "note": None,
        }
    )
    assert len(ex.records) == 2


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        LLMRecord.model_validate(record(smiles="CCO"))


# ----- components -------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"role": "other", "role_other_text": None},
        {"amount_value": 3.0, "amount_text": "1-5"},
        {"amount_basis": None},
        {"amount_basis": "unspecified", "confidence": "high"},
        {"refs": []},
        {"nonvolatile_content_pct": 150.0},
    ],
    ids=[
        "other_without_text",
        "value_and_text",
        "no_basis",
        "unspecified_high",
        "no_refs",
        "nv_pct",
    ],
)
def test_component_hard_rules(overrides):
    with pytest.raises(ValidationError):
        LLMComponent.model_validate(component(**overrides))


def test_component_allowed_cases():
    LLMComponent.model_validate(component(amount_basis="unspecified", confidence="low"))
    LLMComponent.model_validate(component(amount_value=None, amount_text="1-5 (range)"))
    LLMComponent.model_validate(
        component(role="solvent", amount_value=None, amount_unit=None, amount_basis=None)
    )
    LLMComponent.model_validate(component(role="other", role_other_text="defoamer"))


def test_codename_component_with_multiple_refs():
    defn = {
        "block_id": "p-0061",
        "location": "Synthesis Example 2, [0061]",
        "quote": "PAG-2: triphenylsulfonium nonaflate",
        "purpose": "codename_definition",
    }
    c = LLMComponent.model_validate(
        component(definition_location="Synthesis Example 2, [0061]", refs=[REF, defn])
    )
    assert [r.purpose for r in c.refs] == ["value", "codename_definition"]


# ----- exposure / dose --------------------------------------------------


@pytest.mark.parametrize(
    "source,unit,ok",
    [
        ("i-line_365", "mJ/cm2", True),
        ("i-line_365", "uC/cm2", False),
        ("ebeam", "uC/cm2", True),
        ("ebeam", "pC/cm", True),
        ("ebeam", "mJ/cm2", False),
        ("ion_beam", "ions/cm2", True),
        ("other", "other", True),
        (None, "mJ/cm2", True),
    ],
)
def test_dose_unit_family(source, unit, ok):
    rec = with_exposure(
        source=source, dose_unit=unit, ebeam_kv=100.0 if source == "ebeam" else None
    )
    if ok:
        LLMRecord.model_validate(rec)
    else:
        with pytest.raises(ValidationError):
            LLMRecord.model_validate(rec)


def test_intensity_times_time_keeps_dose_null():
    rec = LLMRecord.model_validate(
        with_exposure(
            dose=None,
            dose_unit=None,
            intensity_mw_cm2=10.0,
            exposure_time=15.0,
            exposure_time_unit="s",
        )
    )
    assert rec.process.exposure.dose is None
    assert rec.warnings() == []


def test_dose_without_unit_is_rejected():
    """Checklist: 'Dose unit as printed'. A bare number cannot be placed in a dose family."""
    with pytest.raises(ValidationError, match="dose given without dose_unit"):
        LLMRecord.model_validate(with_exposure(dose=30.0, dose_unit=None))
    with pytest.raises(ValidationError, match="dose given without dose_unit"):
        Exposure.model_validate({"source": "i-line_365", "dose": 30.0})


def test_exposure_values_need_refs_but_empty_group_does_not():
    with pytest.raises(ValidationError):
        LLMRecord.model_validate(with_exposure(refs=[]))
    empty = {k: None for k in exposure()} | {"refs": []}
    LLMRecord.model_validate(with_exposure(**empty))


# ----- bakes ------------------------------------------------------------


def test_room_temperature_is_text():
    rec = record()
    rec["process"]["development"] = {
        "developer_name": "TMAH",
        "concentration": "2.38 wt%",
        "time": 60.0,
        "time_unit": "s",
        "temp_value": None,
        "temp_text": "RT",
        "method": "puddle",
        "rinse": "DI water",
        "refs": [REF],
    }
    assert LLMRecord.model_validate(rec).process.development.temp_text == "RT"
    rec["process"]["development"]["temp_value"] = 23.0
    with pytest.raises(ValidationError):
        LLMRecord.model_validate(rec)


def test_bake_step_value_and_text_conflict():
    rec = record()
    rec["process"]["softbake"]["steps"][0]["temp_text"] = "65 °C"
    with pytest.raises(ValidationError):
        LLMRecord.model_validate(rec)


# ----- results ----------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"value": None, "value_qualitative": None, "figure_only": False},
        {"metric": "ler_3sigma_nm", "sigma": 2},
        {"metric": "sensitivity_unspecified", "confidence": "high"},
        {"refs": []},
        {"metric": "dose_sat", "threshold_pct": 120.0},
        {"value": 200.0, "figure_only": True},
        {"metric_as_written": "   "},
        {"metric": "other", "metric_as_written": ""},
    ],
    ids=[
        "no_evidence",
        "sigma_2",
        "unspecified_high",
        "no_refs",
        "threshold",
        "digitized_figure",
        "blank_metric_as_written",
        "other_without_wording",
    ],
)
def test_result_hard_rules(overrides):
    with pytest.raises(ValidationError):
        LLMResult.model_validate(result(**overrides))


def test_figure_only_value_rejected_in_full_record_too():
    """Guide: don't digitize plots; enforced on gold/adapter records as well."""
    with pytest.raises(ValidationError, match="never read values off plots"):
        Result.model_validate(
            {"metric": "d50", "metric_as_written": "D50", "value": 12.0, "figure_only": True}
        )
    Result.model_validate(
        {"metric": "other", "metric_as_written": "etch resistance", "value_qualitative": "good"}
    )


def test_result_allowed_cases():
    LLMResult.model_validate(result(value=None, figure_only=True, note="Fig. 4 shows 200 nm L/S"))
    LLMResult.model_validate(
        result(
            metric="adhesion", value=None, value_qualitative="○", scale="○: no peeling; ×: peeling"
        )
    )
    LLMResult.model_validate(
        result(
            metric="sensitivity_esize",
            value=None,
            value_qualitative="1.2x",
            reference_example_label="Example 1",
            condition="target 1 µm L/S",
        )
    )


# ----- warnings ---------------------------------------------------------


def test_warnings():
    rec = record()
    rec["components"][1] = component(amount_value=0.0)
    rec["process"]["exposure"] = exposure(
        source="ebeam",
        dose_unit="uC/cm2",
        intensity_mw_cm2=10.0,
        exposure_time=15.0,
        exposure_time_unit="s",
    )
    rec["results"] = [result(metric="dose_sat"), result(metric="ler_3sigma_nm", unit="nm")]
    w = "\n".join(LLMRecord.model_validate(rec).warnings())
    assert "components[1].amount_value is 0" in w
    assert "ebeam exposure without ebeam_kv" in w
    assert "intensity x time" in w
    assert "dose_sat without threshold_pct" in w
    assert "roughness without sigma" in w


def test_missing_units_warn():
    rec = record()
    rec["components"][1] = component(amount_unit=None)
    rec["process"]["softbake"]["steps"][1]["time_unit"] = None
    rec["process"]["exposure"] = exposure(
        dose=None,
        dose_unit=None,
        intensity_mw_cm2=10.0,
        exposure_time=15.0,
        exposure_time_unit=None,
    )
    w = "\n".join(LLMRecord.model_validate(rec).warnings())
    assert "components[1] (PAG-2): amount without amount_unit" in w
    assert "process.softbake.steps[1]: time without time unit" in w
    assert "process.exposure.exposure_time: time without time unit" in w
    assert "softbake.steps[0]" not in w


def test_wt_pct_over_100_warns_probably_parts():
    rec = record()
    rec["components"] = [
        component(
            role="resin", name_as_written="R", amount_value=100.0, amount_basis="wt_pct_solids"
        ),
        component(amount_value=10.0, amount_basis="wt_pct_solids"),
    ]
    assert any("probably parts" in w for w in LLMRecord.model_validate(rec).warnings())


# ----- full record ------------------------------------------------------


def test_full_record_accepts_raw_forms():
    rec = FormulationRecord.model_validate(
        {
            "record_id": "US20080241753A1_ex1",
            "provenance": {"source_type": "patent", "doc_id": "US20080241753A1"},
            "components": [
                {
                    "role": "resin",
                    "name_as_written": "resin X1",
                    "amount_raw": 100,
                    "amount_unit": "parts",
                    "amount_basis": "parts_per_100_resin",
                },
                {"role": "pag", "name_as_written": "PAG", "amount_raw": "1-10"},
            ],
            "process": {
                "peb_temp": "RT",
                "softbake_steps": [{"temp": 95, "time": 1, "time_unit": "min"}],
            },
        }
    )
    assert rec.components[1].amount_raw == "1-10"
    assert rec.process.exposure.dose is None


def test_full_record_rules():
    with pytest.raises(ValidationError):
        Component.model_validate({"role": "other", "name_as_written": "x"})
    with pytest.raises(ValidationError):
        FormulationRecord.model_validate(
            {
                "record_id": "x",
                "provenance": {"source_type": "patent", "doc_id": "x"},
                "process": {"exposure": {"source": "ebeam", "dose_unit": "mJ/cm2"}},
            }
        )


def test_fixtures_are_not_mutated():
    a = record()
    b = copy.deepcopy(a)
    LLMRecord.model_validate(a)
    assert a == b
