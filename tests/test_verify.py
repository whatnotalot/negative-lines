"""Quote verification against the cited blocks (negative_lines.extract.verify)."""

from __future__ import annotations

import json
from pathlib import Path

from builders import component, record, ref, result

from negative_lines.extract.verify import QuoteIndex, check_record, summarize, warnings_from
from negative_lines.ingest.document import SourceDocument
from negative_lines.schema.llm import LLMRecord

FIXTURE = Path(__file__).parent / "fixtures" / "ingest" / "expected_blocks.json"
DOC = SourceDocument.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8"))["document"])
IDX = QuoteIndex(DOC)


def status(block_id: str, quote: str) -> tuple[str, tuple[str, ...]]:
    c = IDX.check(LLMRecord.model_fields["refs"].annotation.__args__[0](  # SourceRef
        block_id=block_id, location="x", quote=quote, purpose="value"), "t")  # fmt: skip
    return c.status, c.found_in


def test_exact_and_normalized_quotes():
    assert status("p-0050", "3.0 parts of PAG-1")[0] == "ok"
    assert status("p-0050", "3.0  PARTS of  pag-1")[0] == "ok"  # case and whitespace
    assert status("t-1-r-3", "Resin A | 100")[0] == "ok"
    assert status("t-1-r-3", "Resin A 100")[0] == "ok"  # cell separator ignored


def test_merged_rows_accept_either_form():
    # quote spans the wrapped physical rows: fine when citing the merged row ...
    assert status("t-3-r-3-4", "PAG-1 (3.0 parts by mass)")[0] == "ok"
    # ... or one of its physical rows
    assert status("t-3-r-3", "PAG-1 (3.0 parts by mass)")[0] == "ok_merged"
    # and a fragment of a physical row while citing the merged row
    assert status("t-3-r-3-4", "1 to 2")[0] == "ok"


def test_wrong_block_and_invented_quotes():
    st, found = status("t-2-r-2", "3.0 parts of PAG-1")
    assert st == "elsewhere" and found == ("p-0050",)
    assert status("t-2-r-2", "PAG-1 (10 parts by weight)")[0] == "not_found"
    assert status("t-9-r-1", "3.0 parts of PAG-1") == ("unknown_block", ("p-0050",))
    # a quote spanning a merged row is reported at the merged row, not its physical rows
    # (it occurs in two merged rows of the fixture: Examples 1 to 2 and Comparative Example 1)
    assert status("p-0050", "PAG-1 (3.0 parts by mass)") == (
        "elsewhere",
        ("t-3-r-3-4", "t-3-r-5-6"),
    )


def test_check_record_and_warnings():
    good = ref("t-3-r-3-4", "Table 3, rows 3-4", "PAG-1 (3.0 parts by mass)")
    bad = ref("t-2-r-2", "Table 2, row 2", "3.0 parts of PAG-1")
    rec = LLMRecord.model_validate(
        record(
            refs=[good],
            components=[component(refs=[good, bad])],
            results=[result(refs=[ref("t-2-r-2", "Table 2", "invented 999 nm")])],
        )  # fmt: skip
    )
    rec.process.softbake.refs.clear()
    checks = check_record(rec, DOC)
    s = summarize(checks)
    # record + component 'good' verified; component 'bad' elsewhere; result invented;
    # the builder's default exposure ref cites p-0045, which this fixture does not have
    assert (s["total"], s["verified"], s["elsewhere"], s["not_found"], s["unknown_block"]) == (
        5,
        2,
        1,
        1,
        1,
    )
    w = warnings_from(checks)
    assert any("components[0] PAG-2 -> t-2-r-2: quote is not in the cited block (found in p-0050)"
               in x for x in w)  # fmt: skip
    assert any("results[0] dose_gel -> t-2-r-2: quote not found" in x for x in w)
