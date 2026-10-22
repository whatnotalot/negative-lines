"""Ingestion fixture: synthetic Google-Patents HTML + expected parsed blocks.

The fixture and its expected parse are checked for internal consistency now;
the parser comparison runs once ``negative_lines.ingest.google_patents``
exists (step 5) and is skipped until then.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

from negative_lines.ingest.document import SourceDocument

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"
HTML_PATH = FIXTURES / "synthetic_google_patent.html"
EXPECTED = json.loads((FIXTURES / "expected_blocks.json").read_text(encoding="utf-8"))

ID_PATTERNS = {
    "abstract": r"abs-\d+",
    "heading": r"h-\d{4}",
    "paragraph": r"p-(\d{4}|u\d{3})",
    "list_item": r"li-\d{4}",
    "table_caption": r"t-\d+-cap",
    "table_row": r"t-\d+-r-\d+",
    "table_row_merged": r"t-\d+-r-\d+-\d+",
    "claim": r"c-\d+",
}


@pytest.fixture(scope="module")
def expected() -> SourceDocument:
    return SourceDocument.model_validate(EXPECTED["document"])


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


@pytest.fixture(scope="module")
def html_text() -> str:
    """Fixture HTML without tags/comments, entities decoded, all whitespace removed."""
    raw = HTML_PATH.read_text(encoding="utf-8")
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    raw = re.sub(r"<head>.*?</head>", "", raw, flags=re.S)
    return _squash(html.unescape(re.sub(r"<[^>]+>", "", raw)))


# ----- the expected parse is well-formed --------------------------------


def test_expected_document_metadata(expected):
    assert expected.doc_id == "SYNTH20260001A1"
    assert (expected.year, expected.language, expected.source_type) == (2026, "en", "patent")
    assert expected.assignee_or_authors == "Example Chemical Co., Ltd."


def test_block_ids_unique_and_follow_conventions(expected):
    ids = [b.block_id for b in expected.blocks]
    assert len(ids) == len(set(ids))
    for b in expected.blocks:
        assert re.fullmatch(ID_PATTERNS[b.kind], b.block_id), b.block_id


def test_paragraph_ids_use_printed_number_not_html_id(expected):
    # <div id="p-0042" num="0041"> -> p-0041 / [0041]
    b = expected.block("p-0041")
    assert b.location == "[0041]" and b.text.startswith("Resin A:")


def test_table_rows_are_consistent(expected):
    for table_id in ("t-1", "t-2", "t-3"):
        rows = [b for b in expected.blocks if b.table_id == table_id and b.kind == "table_row"]
        assert [r.row_index for r in rows] == list(range(1, len(rows) + 1))
        for r in rows:
            assert r.text == " | ".join(r.cells)
            assert r.block_id == f"{table_id}-r-{r.row_index}"
            assert r.location == f"Table {table_id[2:]}, row {r.row_index}"
    # split <table> pieces are one table; spacer rows dropped; wrapped label kept as is
    t1 = [b.cells for b in expected.blocks if b.table_id == "t-1" and b.kind == "table_row"]
    assert t1[1] == ["", "", "Example 1", "Example 2", "Comparative Example 1"]
    assert [c[0] for c in t1[3:5]] == ["Photoacid", "generator"]


def test_every_expected_text_occurs_in_the_html(expected, html_text):
    for b in expected.blocks:
        if b.kind == "table_row_merged":
            continue  # joined text; its physical rows are checked
        parts = b.cells if b.cells is not None else [b.text]
        for part in parts:
            assert _squash(part) in html_text, f"{b.block_id}: {part!r} not in fixture HTML"


def test_merged_rows_are_consistent_with_their_physical_rows(expected):
    from negative_lines.ingest.tables import merge_cells

    merged = [b for b in expected.blocks if b.kind == "table_row_merged"]
    assert [b.block_id for b in merged] == ["t-3-r-1-2", "t-3-r-3-4", "t-3-r-5-6"]
    for m in merged:
        phys = [expected.block(r) for r in m.source_rows]
        assert all(p.merged_into == m.block_id for p in phys)
        assert m.cells == merge_cells([p.cells for p in phys])
        assert m.text == " | ".join(m.cells) and m.row_index == phys[0].row_index
        a, b = m.source_rows[0].rsplit("-", 1)[1], m.source_rows[-1].rsplit("-", 1)[1]
        assert m.block_id == f"{m.table_id}-r-{a}-{b}" and m.location.endswith(f"rows {a}-{b}")
    # physical rows that are not part of a group point nowhere; t-1 'Photoacid'/'generator'
    # (separate value rows) and t-3 row 7 (values in both rows) are not merged
    assert expected.block("t-1-r-4").merged_into is None
    assert expected.block("t-1-r-5").merged_into is None
    assert expected.block("t-3-r-7").merged_into is None
    assert expected.block("t-3-r-3-4").cells == [
        "Examples 1 to 2", "PAG-1 (3.0 parts by mass)", "90° C./90 sec", "120"
    ]  # fmt: skip


def test_fixture_contains_the_cross_reference_cases(expected):
    text = {b.block_id: b.text for b in expected.blocks}
    assert "obtained in Synthesis Example 1" in text["p-0050"]  # codename defined elsewhere
    assert "described in paragraph [0042]" in text["p-0052"]  # paragraph reference
    assert "same manner as in Example 1" in text["p-0052"]  # inherited conditions
    assert "shown in Table 1" in text["p-0053"]  # table reference
    assert "FIG. 3" in text["p-0058"]  # figure-only evidence
    assert "according to claim 1" in text["c-2"]  # claim reference
    assert "PGMEA/PGME (mass ratio 7/3)" in text["p-0050"]  # mixed solvent
    assert "Mw/Mn" in text["p-0041"] and "mJ/cm2" in text["p-0054"]  # sub/sup flattened


def test_render_is_citable_and_excludes_claims(expected):
    out = expected.render()
    assert "[t-1-r-4] Photoacid | PAG-1 | 3.0 | — | 3.0" in out
    assert "[h-0004] ## Example 1" in out
    assert "[li-0055] A: no residue in unexposed areas." in out
    assert "[c-1]" not in out
    # merged rows replace their physical rows in the prompt
    assert "[t-3-r-3-4] Examples 1 to 2 | PAG-1 (3.0 parts by mass) | 90° C./90 sec | 120" in out
    assert "[t-3-r-3]" not in out and "[t-3-r-4]" not in out
    assert "[t-3-r-7]  | 200 | 90° C./90 sec | 95" in out


# ----- parser (step 5) --------------------------------------------------


def test_parser_reproduces_expected_blocks(expected):
    gp = pytest.importorskip(
        "negative_lines.ingest.google_patents", reason="Google Patents parser arrives in step 5"
    )
    parsed = gp.parse_google_patent_html(HTML_PATH.read_text(encoding="utf-8"), url=None)
    assert parsed.model_dump(exclude={"blocks"}) == expected.model_dump(exclude={"blocks"})
    got = [b.model_dump() for b in parsed.blocks]
    want = [b.model_dump() for b in expected.blocks]
    for i, (g, w) in enumerate(zip(got, want, strict=False)):
        assert g == w, f"block {i} ({w['block_id']}) differs"
    assert len(got) == len(want)
