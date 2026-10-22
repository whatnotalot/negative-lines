"""Level-1 integration: map -> extract -> validate -> repair -> enrich, with a fake LLM.

No network. The scripted responses imitate a provider: one invalid extraction
that the repair loop fixes, and one example that stays invalid.
"""

from __future__ import annotations

from builders import component, document_map, record, ref, result
from fakes import FakeStructuredLLM

from negative_lines.config import LLMProfile
from negative_lines.extract import prompts
from negative_lines.extract.pipeline import run_document
from negative_lines.ingest.document import Block, SourceDocument
from negative_lines.llm import JsonCache, StructuredCaller

PROFILE = LLMProfile(name="fake", provider="fake", model="fake-1", api_key_env=None)

DOC = SourceDocument(
    doc_id="SYNTH-0001A",
    title="Negative-tone photosensitive resin composition",
    assignee_or_authors="Example Chemical Co., Ltd.",
    year=2021,
    language="en",
    blocks=[
        Block(
            block_id="h-0007",
            kind="heading",
            section="description",
            location="EXAMPLES",
            text="EXAMPLES",
        ),  # fmt: skip
        Block(
            block_id="p-0050",
            kind="paragraph",
            section="description",
            location="[0050]",
            text="Amounts are parts by mass relative to 100 parts of resin.",
        ),  # fmt: skip
        Block(
            block_id="t-1-r-1",
            kind="table_row",
            section="description",
            location="Table 1, row 1",
            text="Example 1 | 100 | 10 | 3 | 0.3",
            table_id="t-1",
            row_index=1,
            cells=["Example 1", "100", "10", "3", "0.3"],
        ),  # fmt: skip
        Block(
            block_id="c-1",
            kind="claim",
            section="claims",
            location="Claim 1",
            text="1. A composition comprising 1-10 parts of a PAG.",
        ),  # fmt: skip
    ],
)

ROW = ref("t-1-r-1", "Table 1, row 1", "Example 1 | 100 | 10 | 3 | 0.3")


def ex1(confidence: str) -> dict:
    return {
        "example_label": "Example 1",
        "records": [
            record(
                refs=[ROW],
                components=[
                    component(
                        role="resin", name_as_written="Resin A", amount_value=100.0, refs=[ROW]
                    ),  # fmt: skip
                    component(
                        role="crosslinker", name_as_written="C-1", amount_value=10.0, refs=[ROW]
                    ),  # fmt: skip
                    component(name_as_written="PAG-1", amount_value=3.0, refs=[ROW]),
                    component(
                        role="quencher", name_as_written="Q-1", amount_value=0.3, refs=[ROW]
                    ),  # fmt: skip
                    component(
                        role="solvent",
                        name_as_written="PGMEA",
                        amount_value=None,
                        amount_unit=None,
                        amount_basis=None,
                        refs=[ROW],
                    ),  # fmt: skip
                ],
                results=[
                    result(
                        metric="sensitivity_unspecified",
                        metric_as_written="sensitivity",
                        value=120.0,
                        confidence=confidence,
                        refs=[ROW],
                    )
                ],  # fmt: skip
            )
        ],
        "note": None,
    }


def cex1_invalid() -> dict:
    bad = record(example_label="Comparative Example 1", is_comparative=True)
    bad["components"][0]["amount_basis"] = None  # amount without basis: hard error
    return {"example_label": "Comparative Example 1", "records": [bad], "note": None}


def scripted() -> FakeStructuredLLM:
    return FakeStructuredLLM(
        {
            "DocumentMap": [document_map([("Example 1", False), ("Comparative Example 1", True)])],
            "ExampleExtraction": [
                ex1("high"),  # invalid: sensitivity_unspecified needs low confidence
                ex1("low"),  # repaired
                cex1_invalid(),
                cex1_invalid(),  # still invalid after the repair attempt
            ],
        }
    )


def test_pipeline_end_to_end_offline():
    llm = scripted()
    out = run_document(DOC, StructuredCaller(llm, PROFILE, max_repairs=1))

    assert out.map_call.ok
    assert llm.n_calls("DocumentMap") == 1
    assert llm.n_calls("ExampleExtraction") == 4

    # the prompt carries the rendered blocks with their citable IDs, claims excluded
    human = llm.calls["DocumentMap"][0][1][1]
    assert "[t-1-r-1] Example 1 | 100 | 10 | 3 | 0.3" in human
    assert "[h-0007] ## EXAMPLES" in human
    assert "[c-1]" not in human
    assert llm.calls["DocumentMap"][0][0] == ("system", prompts.SYSTEM)

    ok, failed = out.examples
    assert ok.label == "Example 1" and ok.call.ok and ok.call.attempts == 2
    assert failed.label == "Comparative Example 1" and not failed.call.ok
    assert out.failures == [failed]
    assert failed.records == []
    assert any("amount given without amount_basis" in e for e in failed.call.errors)

    (rec,) = out.records
    assert rec.record_id == "SYNTH-0001A_ex1"
    assert rec.provenance.doc_id == "SYNTH-0001A"
    assert rec.provenance.title == DOC.title  # ingested metadata wins
    assert rec.provenance.extraction_model == f"fake:fake-1@{prompts.PROMPT_VERSION}"
    assert rec.provenance.location == "Table 1, row 1"
    wt = [c.amount_wt_pct_solids for c in rec.components]
    assert [round(x, 2) for x in wt[:4]] == [88.26, 8.83, 2.65, 0.26]  # guide's worked example
    assert wt[4] is None
    assert rec.results[0].labeler_confidence == "low"


def test_pipeline_rerun_uses_cache(tmp_path):
    cache = JsonCache(tmp_path)
    first = run_document(DOC, StructuredCaller(scripted(), PROFILE, cache=cache))
    llm = FakeStructuredLLM({})  # would raise if called
    second = run_document(DOC, StructuredCaller(llm, PROFILE, cache=cache))
    assert [r.model_dump() for r in second.records] == [r.model_dump() for r in first.records]
    assert llm.n_calls("DocumentMap") == 0 and llm.n_calls("ExampleExtraction") == 0
    assert second.examples[0].call.cached


def test_pipeline_example_filter_and_unknown_label():
    llm = FakeStructuredLLM(
        {
            "DocumentMap": [document_map([("Example 1", False)])],
            "ExampleExtraction": [ex1("low")],
        }
    )
    out = run_document(DOC, StructuredCaller(llm, PROFILE), examples=["Example 1"])
    assert len(out.records) == 1 and out.warnings == []

    llm = FakeStructuredLLM(
        {"DocumentMap": [document_map([("Example 1", False)])], "ExampleExtraction": [ex1("low")]}
    )
    out = run_document(DOC, StructuredCaller(llm, PROFILE), examples=["Example 9"])
    assert "example 'Example 9' not in document map" in out.warnings
    assert "asked for 'Example 9', record labelled 'Example 1'" in out.warnings


def test_map_failure_stops_before_examples():
    llm = FakeStructuredLLM({"DocumentMap": ["{bad", "{still bad"]})
    out = run_document(DOC, StructuredCaller(llm, PROFILE, max_repairs=1))
    assert not out.map_call.ok and out.examples == []
