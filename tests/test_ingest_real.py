"""OPT-IN: ingest a real development patent from Google Patents.

Deselected by default (marker ``network``); run with::

    uv run pytest -m network -rP

Downloads US20080241753A1 (development patent 06, see eval/split.yaml) once and
caches the raw HTML in data/raw/ (gitignored). No LLM calls. Only development
documents may be used here.
"""

from __future__ import annotations

from collections import Counter

import pytest

from negative_lines.gold.split import get_split
from negative_lines.ingest.google_patents import ingest_google_patent

pytestmark = pytest.mark.network

DOC_ID = "US20080241753A1"


@pytest.fixture(scope="module")
def doc():
    assert get_split().set_of(DOC_ID) == "development"
    return ingest_google_patent(DOC_ID)


def test_metadata(doc):
    assert doc.doc_id == DOC_ID
    assert doc.title == "Negative Resist Composition"
    assert doc.year == 2008 and doc.language == "en"
    assert doc.url.endswith(f"/patent/{DOC_ID}/en")


def test_blocks_are_unique_and_cover_all_sections(doc):
    ids = [b.block_id for b in doc.blocks]
    assert len(ids) == len(set(ids))
    kinds = Counter(b.kind for b in doc.blocks)
    assert kinds["paragraph"] > 150 and kinds["claim"] == 9 and kinds["table_caption"] == 3
    assert {b.table_id for b in doc.blocks if b.table_id} == {"t-1", "t-2", "t-3"}
    assert [b.block_id for b in doc.blocks if b.kind == "abstract"][0] == "abs-1"


def test_examples_and_codename_definitions_are_citable(doc):
    headings = [b.text for b in doc.blocks if b.kind == "heading"]
    assert {"EXAMPLES", "Example 1", "Example 2"} <= set(headings)
    assert "Examples 3 to 24 and Comparative Example 1" in headings
    # codename definitions referenced from Table 1
    assert "PAG1 denotes triphenylsulfonium trifluoromethanesulfonate" in doc.block("p-0170").text
    # e-beam conditions and the text/table thickness conflict noted in the gold QC sheet
    assert "70 kV" in doc.block("p-0164").text
    assert doc.block("t-2-r-3").cells[0] == "Example 1"


def test_table_rows_keep_cells_verbatim(doc):
    t1 = [b for b in doc.blocks if b.table_id == "t-1" and b.kind == "table_row"]
    assert t1[0].row_index == 1 and all(b.cells for b in t1)
    assert any("PAG1 (10 parts" in b.text for b in t1)
