"""extract_patent / list_examples / CLI, offline (fake LLM, synthetic fixture document)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from builders import component, document_map, record, ref, result
from fakes import FakeStructuredLLM

from negative_lines import cli
from negative_lines.config import LLMProfile
from negative_lines.extract import api
from negative_lines.extract.api import TooManyExamplesError, extract_patent, list_examples
from negative_lines.gold.split import BenchmarkAccessError, get_split
from negative_lines.ingest.document import SourceDocument

FIXTURE = Path(__file__).parent / "fixtures" / "ingest" / "expected_blocks.json"
DOC = SourceDocument.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8"))["document"])
PROFILE = LLMProfile(name="fake", provider="fake", model="fake-1", api_key_env=None)
ROW = ref("t-1-r-3", "Table 1, row 3", "Resin | Resin A | 100 | 100 | 100")
EXAMPLES = [("Example 1", False), ("Comparative Example 1", True)]


def extraction(label: str, comparative: bool, valid: bool = True) -> dict:
    rec = record(example_label=label, is_comparative=comparative, refs=[ROW],
                 components=[component(role="resin", name_as_written="Resin A",
                                       amount_value=100.0, refs=[ROW]),
                             component(name_as_written="PAG-1", refs=[ROW])],
                 results=[result(refs=[ROW])])  # fmt: skip
    if not valid:
        rec["components"][1]["amount_basis"] = None
    return {"example_label": label, "records": [rec], "note": None}


def fake(*ex_responses, examples=EXAMPLES) -> FakeStructuredLLM:
    return FakeStructuredLLM(
        {
            "DocumentMap": [document_map(examples, doc_id=DOC.doc_id)],
            "ExampleExtraction": list(ex_responses),
        }
    )


def run(llm, **kw):
    kw = {"profile": PROFILE, "use_cache": False, "llm": llm} | kw
    return extract_patent(DOC, **kw)


def test_extract_writes_records_and_run_metadata(tmp_path):
    llm = fake(extraction("Example 1", False), extraction("Comparative Example 1", True))
    out = run(llm, out_dir=tmp_path)
    assert [r.record_id for r in out.records] == [f"{DOC.doc_id}_ex1", f"{DOC.doc_id}_cex1"]
    assert out.failures == []

    d = tmp_path / DOC.doc_id / out.run_id
    assert out.paths["run"].parent == d
    lines = (d / "records.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["record_id"] for x in lines] == [r.record_id for r in out.records]
    assert json.loads((d / "failures.json").read_text("utf-8")) == []
    assert (
        json.loads((d / "document_map.json").read_text("utf-8"))["document"]["doc_id"] == DOC.doc_id
    )

    meta = json.loads((d / "run.json").read_text("utf-8"))
    assert meta["model"] == "fake:fake-1" and meta["records"] == 2
    assert meta["examples_in_map"] == ["Example 1", "Comparative Example 1"]
    assert meta["usage"]["calls"] == 3 and meta["usage"]["input_tokens"] == 30
    assert meta["split_set"] is None
    # quote verification: Table 1 row refs verified; builder default refs cite p-0045,
    # which the fixture does not have
    rc = meta["ref_checks"]
    assert rc["total"] > 0 and rc["ok"] > 0 and rc["unknown_block"] > 0
    assert [e["example"] for e in meta["per_example"]] == ["Example 1", "Comparative Example 1"]
    assert any("unknown block p-0045" in w for w in out.records[0].warnings)
    assert any("not in eval/split.yaml" in n for n in meta["notes"])


def test_extract_selected_examples_and_failures(tmp_path):
    llm = fake(extraction("Comparative Example 1", True, valid=False),
               extraction("Comparative Example 1", True, valid=False))  # fmt: skip
    out = run(llm, examples=["Comparative Example 1"], out_dir=tmp_path)
    assert out.records == [] and [f.label for f in out.failures] == ["Comparative Example 1"]
    (fail,) = json.loads(out.paths["failures"].read_text("utf-8"))
    assert fail["attempts"] == 2 and fail["raw"] is not None
    assert "amount given without amount_basis" in fail["errors"][0]


def test_no_write_when_out_dir_is_none():
    out = run(fake(extraction("Example 1", False)), examples=["Example 1"], out_dir=None)
    assert out.paths == {} and len(out.records) == 1


def test_benchmark_documents_are_refused_before_any_call():
    bench_id = get_split().doc_ids("benchmark")[0]
    doc = DOC.model_copy(update={"doc_id": bench_id})
    llm = FakeStructuredLLM({})  # raises if called
    with pytest.raises(BenchmarkAccessError):
        extract_patent(doc, profile=PROFILE, llm=llm, use_cache=False, out_dir=None)
    with pytest.raises(BenchmarkAccessError):
        list_examples(doc, profile=PROFILE, llm=llm, use_cache=False)
    assert llm.n_calls("DocumentMap") == 0


def test_max_examples_is_optional_and_checked_before_example_calls():
    with pytest.raises(TooManyExamplesError):
        run(FakeStructuredLLM({}), examples=["Example 1", "Example 2"], max_examples=1,
            out_dir=None)  # fmt: skip
    llm = fake()
    with pytest.raises(TooManyExamplesError, match="lists 2 examples"):
        run(llm, max_examples=1, out_dir=None)
    assert llm.n_calls("DocumentMap") == 1 and llm.n_calls("ExampleExtraction") == 0
    # within the cap: the map is reused, not requested twice
    llm = fake(extraction("Example 1", False), extraction("Comparative Example 1", True))
    out = run(llm, max_examples=5, out_dir=None)
    assert len(out.records) == 2 and llm.n_calls("DocumentMap") == 1


def test_list_examples():
    assert list_examples(DOC, profile=PROFILE, llm=fake(), use_cache=False) == EXAMPLES


# ----- CLI ------------------------------------------------------------------


@pytest.fixture()
def offline_cli(monkeypatch):
    holder = {}
    monkeypatch.setattr(cli, "_ingest", lambda doc_id: DOC.model_copy(update={"doc_id": doc_id}))
    monkeypatch.setattr(api, "build_chat_model", lambda profile: holder["llm"])
    monkeypatch.setattr(api, "load_llm_profile", lambda name=None: PROFILE)
    return holder


def test_cli_extract(offline_cli, tmp_path, capsys):
    offline_cli["llm"] = fake(extraction("Example 1", False))
    code = cli.main(["extract", DOC.doc_id, "-e", "Example 1", "--no-cache",
                     "--out-dir", str(tmp_path)])  # fmt: skip
    out = capsys.readouterr().out
    assert code == 0
    assert "examples: 1 requested, 1 ok, 0 failed; records: 1" in out
    assert "Example 1: ok, 1 record(s), 1 attempt(s)" in out
    assert "written:" in out and any(tmp_path.rglob("records.jsonl"))


def test_cli_extract_reports_failures_with_exit_1(offline_cli, capsys):
    bad = extraction("Example 1", False, valid=False)
    offline_cli["llm"] = fake(bad, bad)
    code = cli.main(["extract", DOC.doc_id, "-e", "Example 1", "--no-cache", "--no-write"])
    assert code == 1
    assert "Example 1: FAILED" in capsys.readouterr().out


def test_cli_examples_and_benchmark_refusal(offline_cli, capsys):
    offline_cli["llm"] = fake()
    assert cli.main(["examples", DOC.doc_id, "--no-cache"]) == 0
    assert "Comparative Example 1  (comparative)" in capsys.readouterr().out
    offline_cli["llm"] = FakeStructuredLLM({})
    assert cli.main(["extract", get_split().doc_ids("benchmark")[0], "--no-write"]) == 2
    assert "refused:" in capsys.readouterr().err


def test_cli_ingest(offline_cli, capsys):
    assert cli.main(["ingest", DOC.doc_id, "--blocks", "2"]) == 0
    out = capsys.readouterr().out
    assert f"blocks: {len(DOC.blocks)}" in out and "[abs-1]" in out
