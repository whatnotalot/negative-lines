"""Consistency warnings, rule metadata and variant warnings (regression tests for the
failures seen on US20080241753A1 Example 3; synthetic data only)."""

from __future__ import annotations

import pytest
from builders import bake, coating, component, document_map, exposure, record, ref, result
from fakes import FakeStructuredLLM
from synthetic_docs import range_section_doc

from negative_lines.config import REPO_ROOT, LLMProfile
from negative_lines.extract import prompts
from negative_lines.extract.pipeline import run_document
from negative_lines.extract.rules import RULES, assumptions
from negative_lines.llm import StructuredCaller
from negative_lines.schema.llm import LLMRecord
from negative_lines.schema.validators import expected_source


def warnings_for(**kw) -> list[str]:
    return [
        w for w in LLMRecord.model_validate(record(**kw)).warnings() if w.startswith("consistency")
    ]


def with_exposure(**kw) -> dict:
    rec = record()
    rec["process"]["exposure"] = exposure(**kw)
    return rec


def consistency(rec: dict) -> list[str]:
    return [w for w in LLMRecord.model_validate(rec).warnings() if w.startswith("consistency")]


# ----- exposure -------------------------------------------------------------


@pytest.mark.parametrize(
    "tool,expected",
    [
        ("electron beam writer (HL-800D)", "ebeam"),
        ("EB lithography system", "ebeam"),
        ("EUV interference lithography (13.5 nm)", "EUV_13.5"),
        ("KrF excimer laser stepper", "KrF_248"),
        ("SUSS MJB4; i-line and g-line mixed line", "mixed_lines"),
        ("X-ray irradiation apparatus", "other"),
        ("contact aligner", None),
        (None, None),
    ],
)
def test_expected_source(tool, expected):
    assert expected_source(tool) == expected


@pytest.mark.parametrize(
    "source,dose_unit",
    [("EUV_13.5", "mJ/cm2"), ("other", "uC/cm2"), (None, None)],
    ids=["euv", "other", "unset"],
)
def test_ebeam_tool_with_other_source_warns(source, dose_unit):
    w = consistency(with_exposure(source=source, dose=None if dose_unit is None else 10.0,
                                  dose_unit=dose_unit, tool="electron beam writer"))  # fmt: skip
    assert any("implies source 'ebeam'" in x for x in w)


def test_kv_without_ebeam_and_matching_tool_is_quiet():
    w = consistency(with_exposure(source="other", dose=None, dose_unit=None, ebeam_kv=70.0))
    assert any("ebeam_kv given but source is 'other'" in x for x in w)
    ok = with_exposure(source="ebeam", dose=None, dose_unit=None, ebeam_kv=70.0,
                       tool="electron beam writer")  # fmt: skip
    assert consistency(ok) == []


# ----- components -------------------------------------------------------------


def test_role_and_basis_warnings():
    rec = record(components=[
        component(role="resin", name_as_written="Resin 1", amount_value=100.0,
                  amount_basis="parts_by_mass"),
        component(role="acid_amplifier", name_as_written="PAG1", amount_basis="parts_by_mass"),
        component(role="additive", name_as_written="Trioctylamine", amount_value=0.8,
                  amount_basis="parts_by_mass"),
        component(role="solvent", name_as_written="PM/PE = 3/7", amount_value=None,
                  amount_unit=None, amount_basis=None),
    ])  # fmt: skip
    w = "\n".join(consistency(rec))
    assert "(PAG1) looks like a photoacid generator but role is 'acid_amplifier'" in w
    assert "(Trioctylamine) is an amine (usually 'quencher') but role is 'additive'" in w
    assert "basis 'parts_by_mass' although the resin is 100 parts" in w
    assert "(PM/PE = 3/7) looks like a mixed solvent" in w


def test_correct_components_are_quiet():
    rec = record(components=[
        component(role="resin", name_as_written="Resin 1", amount_value=100.0),
        component(role="pag", name_as_written="PAG1"),
        component(role="quencher", name_as_written="Trioctylamine", amount_value=0.8),
        component(role="solvent", name_as_written="PM", amount_value=3.0, amount_unit=None,
                  amount_basis="solvent_ratio_unspecified"),
    ])  # fmt: skip
    assert consistency(rec) == []


# ----- process ------------------------------------------------------------------


def test_film_equal_to_underlayer_and_rt_softbake_step():
    rec = record()
    rec["process"]["coating"] = coating(film_thickness=420.0, film_thickness_unit="nm",
                                        underlayer="novolak resin, 230 °C 90 s, 420 nm")  # fmt: skip
    rec["process"]["softbake"]["steps"].append(
        {"temp_value": None, "temp_text": "RT", "time": None, "time_unit": None}
    )
    w = "\n".join(consistency(rec))
    assert "resist film_thickness 420 equals the underlayer thickness" in w
    assert "softbake step 3 at RT without time" in w
    rec["process"]["coating"] = coating(film_thickness=100.0, film_thickness_unit="nm",
                                        underlayer="novolak resin, 420 nm")  # fmt: skip
    rec["process"]["softbake"]["steps"].pop()
    assert consistency(rec) == []


# ----- rules metadata ---------------------------------------------------------


def test_every_rule_has_a_basis_and_source_and_is_in_the_prompt():
    assert len({r.id for r in RULES}) == len(RULES)
    for r in RULES:
        assert r.basis in ("vocab", "guide", "schema", "assumption") and r.source
        assert r.text in prompts.SYSTEM
    assert {r.id for r in assumptions()} >= {"role-nitrogen-compound", "inherited-conditions"}


def test_readme_lists_the_assumptions_for_team_confirmation():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for r in assumptions():
        assert f"`{r.id}`" in readme, f"README does not list assumption {r.id}"


# ----- record boundaries: variant warning in the pipeline -------------------


PROFILE = LLMProfile(name="fake", provider="fake", model="fake-1", api_key_env=None)


def ex3_extraction(n_records: int) -> dict:
    row = ref("t-2-r-2", "Table 2, row 2", "Example 3 | 100/200")
    recs = []
    for i in range(n_records):
        r = record(example_label="Example 3", variant_label=f"film {100 * (i + 1)} nm" if n_records > 1 else None,
                   refs=[row], components=[component(role="resin", name_as_written="Resin 1",
                   amount_value=100.0, refs=[row])], results=[result(refs=[row])])  # fmt: skip
        r["process"]["peb"] = bake(refs=[row])
        recs.append(r)
    return {"example_label": "Example 3", "records": recs, "note": None}


@pytest.mark.parametrize("n,warns", [(1, True), (2, False)])
def test_variant_warning_when_hint_but_single_record(n, warns):
    doc = range_section_doc()
    llm = FakeStructuredLLM({"DocumentMap": [document_map([("Example 3", False)], doc_id=doc.doc_id)],
                             "ExampleExtraction": [ex3_extraction(n)]})  # fmt: skip
    out = run_document(doc, StructuredCaller(llm, PROFILE), examples=["Example 3"])
    assert len(out.records) == n
    has = any("possible experimental variant" in w for r in out.records for w in r.warnings)
    assert has is warns
    if n == 2:
        assert [r.record_id for r in out.records] == ["SYNTH-CTX-1_ex3_film-100-nm",
                                                      "SYNTH-CTX-1_ex3_film-200-nm"]  # fmt: skip
    # the example prompt carries the per-example context, not the whole document
    prompt = llm.calls["ExampleExtraction"][0][1][1]
    assert "TARGET EXAMPLE: 'Example 3'" in prompt
    assert "## D. Inherited procedure from Example 1" in prompt
    assert "Examples 1 to 2" not in prompt and "[p-0030]" not in prompt
