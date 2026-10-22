"""Step 3: LLMRecord -> FormulationRecord (ids, units, computed fields, provenance)."""

from __future__ import annotations

import pytest
from builders import (
    REF,
    bake,
    coating,
    component,
    development,
    exposure,
    record,
    ref,
    result,
)

from negative_lines.enrich import (
    compute_wt_pct_solids,
    example_slug,
    make_record_id,
    merge_bake_method,
    to_formulation_record,
    to_nm,
    to_seconds,
    unique_id,
)
from negative_lines.schema.enums import VOCAB_VERSION
from negative_lines.schema.llm import DocumentInfo, LLMComponent, LLMRecord

DOC = DocumentInfo(
    source_type="patent",
    doc_id="SYNTH-0001A",
    title="Negative-tone photosensitive resin composition",
    assignee_or_authors="Example Chemical Co., Ltd.",
    year=2021,
    language="en",
)


def comps(*specs: dict) -> list[LLMComponent]:
    return [LLMComponent.model_validate(component(**s)) for s in specs]


def convert(rec: dict, **kw):
    kw = {"document": DOC, "record_id": "SYNTH-0001A_ex1", "extraction_model": "fake:model"} | kw
    return to_formulation_record(LLMRecord.model_validate(rec), **kw)


# ----- record ids (PROVISIONAL convention) -------------------------------


@pytest.mark.parametrize(
    "label,slug",
    [
        ("Example 3", "ex3"),
        ("Example No. 3", "ex3"),
        ("EXAMPLE 12", "ex12"),
        ("Comparative Example 1", "cex1"),
        ("Comparative Examples 2", "cex2"),
        ("Reference Example 1", "rex1"),
        ("Example 1-2", "ex12"),
        ("W1", "w1"),
        ("Sample A", "sample-a"),
    ],
)
def test_example_slug(label, slug):
    assert example_slug(label) == slug


def test_record_id_and_uniqueness():
    assert make_record_id("JP2019123456A", "Comparative Example 1") == "JP2019123456A_cex1"
    assert make_record_id("X", "Example 1", "dose 30 mJ/cm2") == "X_ex1_dose-30-mj-cm2"
    taken: set[str] = set()
    assert [unique_id("X_ex1", taken) for _ in range(3)] == ["X_ex1", "X_ex1_2", "X_ex1_3"]


# ----- units ------------------------------------------------------------


def test_units_follow_vocab_tables():
    assert to_nm(0.4, "um") == 400.0
    assert to_nm(1.5, "µm") == 1500.0
    assert to_nm(500, "Å") == 50.0
    assert to_seconds(3, "min") == 180.0
    assert to_seconds(None, "s") is None
    assert to_nm(5, None) is None
    with pytest.raises(ValueError):
        to_nm(1, "mil")


# ----- wt% of solids ----------------------------------------------------


def test_guide_worked_example_phr():
    """hand-labeling-guide: resin 100, crosslinker 10, PAG 3, quencher 0.3, PGMEA 1500 parts."""
    c = comps(
        {"role": "resin", "name_as_written": "Resin", "amount_value": 100.0},
        {"role": "crosslinker", "name_as_written": "XL", "amount_value": 10.0},
        {"role": "pag", "name_as_written": "PAG", "amount_value": 3.0},
        {"role": "quencher", "name_as_written": "Q", "amount_value": 0.3},
        {"role": "solvent", "name_as_written": "PGMEA", "amount_value": 1500.0},
    )
    wt, warn = compute_wt_pct_solids(c)
    assert [round(x, 2) if x is not None else None for x in wt] == [88.26, 8.83, 2.65, 0.26, None]
    assert warn == []


def test_mass_g_with_nonvolatile_resin_solution():
    c = comps(
        {
            "role": "resin",
            "name_as_written": "varnish",
            "amount_value": 50.0,
            "amount_unit": "g",
            "amount_basis": "mass_g",
            "nonvolatile_content_pct": 40.0,
        },  # fmt: skip
        {
            "role": "pag",
            "name_as_written": "PAG",
            "amount_value": 1.0,
            "amount_unit": "g",
            "amount_basis": "mass_g",
        },  # fmt: skip
    )
    wt, _ = compute_wt_pct_solids(c)
    assert [round(x, 3) for x in wt] == [95.238, 4.762]


def test_wt_pct_solids_is_copied_and_wt_pct_total_renormalized():
    copied, _ = compute_wt_pct_solids(
        comps(
            {
                "role": "resin",
                "name_as_written": "R",
                "amount_value": 97.0,
                "amount_basis": "wt_pct_solids",
            },  # fmt: skip
            {
                "role": "pag",
                "name_as_written": "P",
                "amount_value": 3.0,
                "amount_basis": "wt_pct_solids",
            },  # fmt: skip
        )
    )
    assert copied == [97.0, 3.0]
    total, _ = compute_wt_pct_solids(
        comps(
            {
                "role": "resin",
                "name_as_written": "R",
                "amount_value": 6.0,
                "amount_basis": "wt_pct_total",
            },  # fmt: skip
            {
                "role": "pag",
                "name_as_written": "P",
                "amount_value": 2.0,
                "amount_basis": "wt_pct_total",
            },  # fmt: skip
            {
                "role": "solvent",
                "name_as_written": "S",
                "amount_value": 92.0,
                "amount_basis": "wt_pct_total",
            },  # fmt: skip
        )
    )
    assert total == [75.0, 25.0, None]


@pytest.mark.parametrize(
    "specs,reason",
    [
        (
            [
                {"role": "resin", "name_as_written": "R", "amount_value": 100.0},
                {
                    "role": "quencher",
                    "name_as_written": "Q",
                    "amount_value": 5.0,
                    "amount_basis": "mol_pct_vs_pag",
                },
            ],  # fmt: skip
            "different bases",
        ),
        (
            [
                {
                    "role": "resin",
                    "name_as_written": "R",
                    "amount_value": None,
                    "amount_text": "100-120",
                },  # fmt: skip
                {"role": "pag", "name_as_written": "P", "amount_value": 3.0},
            ],
            "no numeric amount",
        ),
        (
            [
                {
                    "role": "quencher",
                    "name_as_written": "Q",
                    "amount_value": 5.0,
                    "amount_basis": "mol_pct_vs_pag",
                }
            ],  # fmt: skip
            "needs_molar_masses",
        ),
        (
            [
                {"role": "pag", "name_as_written": "P3", "amount_value": 10.0, "mixture_id": "m1"},
                {"role": "pag", "name_as_written": "P4", "amount_value": 10.0, "mixture_id": "m1"},
            ],
            "mixture",
        ),
    ],
    ids=["mixed_bases", "range_amount", "molar_basis", "mixture"],
)
def test_wt_pct_not_computed_when_unsafe(specs, reason):
    wt, warn = compute_wt_pct_solids(comps(*specs))
    assert all(x is None for x in wt)
    assert reason in warn[0]


# ----- bake method (PROVISIONAL) -----------------------------------------


@pytest.mark.parametrize(
    "methods,expected,warns",
    [
        (("hot_plate", None, None), "hot_plate", False),
        (("hot_plate", "unspecified", "hot_plate"), "hot_plate", False),
        (("unspecified", None, None), "unspecified", False),
        ((None, None, None), None, False),
        (("hot_plate", "oven", None), None, True),
    ],
)
def test_merge_bake_method(methods, expected, warns):
    value, warning = merge_bake_method(*methods)
    assert value == expected
    assert (warning is not None) == warns


# ----- full conversion --------------------------------------------------


def full_llm_record() -> dict:
    defn = ref("p-0042", "[0042]", "PAG-1: triphenylsulfonium nonaflate", "codename_definition")
    shared = ref("p-0051", "[0051]", "Unless otherwise stated", "shared_condition")
    row = ref("t-1-r-1", "Table 1, row 1", "Example 1 | Resin A 100 | PAG-1 3.0")
    rec = record(
        solids_content_wt_pct=30.0,
        refs=[shared, row],
        components=[
            component(
                role="resin",
                name_as_written="Resin A",
                amount_value=100.0,
                refs=[row],
                polymer={
                    "repeat_units": "p-hydroxystyrene / styrene",
                    "monomer_ratio": "80/20 mol",
                    "mw": 8000.0,
                    "pdi": 1.6,
                },
            ),  # fmt: skip
            component(
                name_as_written="PAG-1", refs=[row, defn], definition_location="[0042]"
            ),  # fmt: skip
            component(
                role="solvent",
                name_as_written="PGMEA",
                amount_value=7.0,
                amount_unit=None,
                amount_basis="solvent_mass_ratio",
                refs=[REF],
            ),  # fmt: skip
        ],
        results=[
            result(
                metric="sensitivity_esize",
                metric_as_written="Eop",
                value=120.0,
                pitch_value=4.0,
                pitch_unit="um",
                pattern_type="line_space",
                condition="2 um L/S 1:1",
            ),  # fmt: skip
            result(
                metric="resolution_min_cd_nm",
                metric_as_written="Resolution",
                value=1.5,
                unit="um",
                film_thickness=1.0,
                film_thickness_unit="um",
            ),  # fmt: skip
            result(
                metric="sensitivity_esize",
                metric_as_written="sensitivity",
                value=None,
                unit=None,
                value_qualitative="1.2x",
                reference_example_label="Comparative Example 1",
            ),  # fmt: skip
        ],
    )
    rec["process"] = {
        "coating": coating(refs=[shared]),
        "softbake": rec["process"]["softbake"] | {"refs": [shared]},
        "exposure": exposure(
            dose=None,
            dose_unit=None,
            intensity_mw_cm2=10.0,
            exposure_time=15.0,
            exposure_time_unit="s",
            refs=[shared],
        ),  # fmt: skip
        "peb": bake(method="hot_plate", refs=[shared]),
        "development": development(refs=[shared]),
        "hardbake": bake(
            temp_value=None,
            temp_text="150-160 °C",
            time=1.0,
            time_unit="h",
            method="oven",
            refs=[shared],
        ),  # fmt: skip
    }
    return rec


def test_full_conversion():
    out = convert(
        full_llm_record(),
        map_is_comparative=False,
        resolve_example=lambda lbl: make_record_id("SYNTH-0001A", lbl),
    )
    assert out.record_id == "SYNTH-0001A_ex1"
    assert out.vocab_version == VOCAB_VERSION
    assert out.solids_content_wt_pct == 30.0

    p = out.provenance
    assert (p.doc_id, p.source_type, p.year) == ("SYNTH-0001A", "patent", 2021)
    assert p.location == "Table 1, row 1"  # first 'value' ref, not the shared condition
    assert p.evidence_snippet.startswith("Example 1 | Resin A")
    assert p.extraction_model == "fake:model"
    assert p.confidence is None and p.human_verified is False
    assert p.labeler_confidence == "high"

    resin, pag, solvent = out.components
    assert resin.polymer.monomer_ratio == "80/20 mol"
    assert resin.amount_raw == 100.0 and resin.amount_wt_pct_solids == pytest.approx(97.087, 1e-3)
    assert [r.purpose for r in pag.refs] == ["value", "codename_definition"]
    assert solvent.amount_wt_pct_solids is None

    pr = out.process
    assert (pr.substrate, pr.film_thickness, pr.film_thickness_unit) == ("silicon wafer", 1.0, "um")
    assert [(s.temp, s.time, s.time_unit) for s in pr.softbake_steps] == [
        (65.0, 1.0, "min"),
        (95.0, 3.0, "min"),
    ]
    assert pr.exposure.dose is None
    assert pr.exposure.exposure_time_s == 15.0
    assert pr.exposure.dose_computed == 150.0  # 10 mW/cm2 x 15 s
    assert (pr.peb_temp, pr.peb_time, pr.peb_time_unit) == (95.0, 2.0, "min")
    assert pr.developer.temp == "RT" and pr.rinse == "pure water"
    assert pr.hardbake_temp == "150-160 °C"
    assert pr.bake_method is None  # hot_plate vs oven -> left null with warning
    assert set(pr.refs) == {"coating", "softbake", "exposure", "peb", "development", "hardbake"}

    eop, res, rel = out.results
    assert eop.pitch_nm == 4000.0 and eop.value == 120.0
    assert res.value == 1.5 and res.unit == "um" and res.film_thickness == 1000.0
    assert rel.reference_record_id == "SYNTH-0001A_cex1"
    assert any("bake methods differ" in w for w in out.warnings)


def test_conversion_warnings_propagate():
    rec = record()
    rec["components"][1] = component(amount_value=0.0)
    out = convert(rec, map_is_comparative=True)
    assert any("amount_value is 0" in w for w in out.warnings)
    assert any("is_comparative differs" in w for w in out.warnings)
    assert out.provenance.is_comparative is False  # record value kept (PROVISIONAL)


def test_result_length_without_unit_is_not_converted():
    rec = record(results=[result(metric="resolution_min_cd_nm", value=2.0, unit="um",
                                 pitch_value=4.0, pitch_unit=None)])  # fmt: skip
    out = convert(rec)
    assert out.results[0].pitch_nm is None
    assert any("pitch without unit" in w for w in out.warnings)
