"""Per-example context assembly and example-label parsing (synthetic documents).

Regression tests for the failures of the first real extraction (US20080241753A1,
Example 3): values taken from another example's table row, quotes from another
example's text, variants not split.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from synthetic_docs import range_section_doc

from negative_lines.extract.context import build_example_context, sections
from negative_lines.extract.labels import heading_keys, keys_in, label_key
from negative_lines.ingest.document import SourceDocument

DOC = range_section_doc()
FIXTURE = Path(__file__).parent / "fixtures" / "ingest" / "expected_blocks.json"
HTML_DOC = SourceDocument.model_validate(
    json.loads(FIXTURE.read_text(encoding="utf-8"))["document"]
)


def ids(ctx, group):
    return [b.block_id for b in ctx.groups[group]]


# ----- labels ---------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "In Examples 3, 5, 7 and 23, the same",
            {("ex", "3"), ("ex", "5"), ("ex", "7"), ("ex", "23")},
        ),
        ("Examples 1 to 4", {("ex", str(i)) for i in range(1, 5)}),
        ("Comparative Examples 1 and 2", {("cex", "1"), ("cex", "2")}),
        ("Example 1-1 to 1-3", {("ex", "1-1"), ("ex", "1-2"), ("ex", "1-3")}),
        ("Synthesis Example 2", {("syn", "2")}),
        ("Embodiment 12", {("ex", "12")}),
        ("Example No. 3", {("ex", "3")}),
        ("no examples here", set()),
    ],
)
def test_keys_in(text, expected):
    assert keys_in(text) == expected


def test_label_and_heading_keys():
    assert label_key("Comparative Example 1") == ("cex", "1")
    assert label_key("Example 21 (composition W1 of Example 9)") == ("ex", "21")
    assert label_key("Synthesis") is None
    assert heading_keys("Two-Layer Resist Method") == set()
    assert ("cex", "1") in heading_keys("Examples 3 to 5 and Comparative Example 1")


def test_sections_split_at_example_and_major_headings():
    secs = {s.heading.text if s.heading else None: s for s in sections(DOC)}
    ex1 = secs["Example 1"]
    assert ex1.keys == {("ex", "1")}
    # the sub-heading belongs to Example 1, the next example heading starts a new section
    assert [b.block_id for b in ex1.blocks] == ["h-0012", "h-0013", "p-0020", "p-0021", "p-0022",
                                                "p-0023", "p-0024"]  # fmt: skip
    assert secs["INDUSTRIAL APPLICABILITY"].keys == set()


# ----- Example 3 (range section, inherits Example 1) -------------------------


@pytest.fixture(scope="module")
def ex3():
    return build_example_context(DOC, None, "Example 3")


def test_own_section_and_table_rows_only_for_the_target(ex3):
    assert ids(ex3, "own") == ["h-0015", "p-0040", "p-0041"]
    # formulation row 'Examples 3 to 4', not 'Examples 1 to 2' or the comparative row;
    # conditions row 'Example 3' only; captions and header rows kept
    assert ids(ex3, "tables") == ["t-1-cap", "t-1-r-1", "t-1-r-3", "t-2-cap", "t-2-r-1", "t-2-r-2"]
    assert ids(ex3, "mentions") == ["p-0060"]


def test_inherits_only_the_explicitly_named_example(ex3):
    assert [lbl for lbl, _ in ex3.inherited_from] == ["Example 1"]
    assert "[p-0040]" in ex3.inherited_from[0][1]
    assert ids(ex3, "inherited") == ["h-0012", "h-0013", "p-0020", "p-0021", "p-0022", "p-0023",
                                     "p-0024"]  # fmt: skip
    assert "p-0030" not in ex3.block_ids()  # Example 2's procedure is for Examples 4 / Comp. 1


def test_definitions_include_synthesis_and_codenames(ex3):
    assert "p-0010" in ids(ex3, "definitions")  # Synthesis Example 1, via the inherited text
    assert "p-0041" in ids(ex3, "own")  # PAG1 / PM / PE definitions


def test_variant_hint_for_thickness_pair_but_not_solvent_ratio(ex3):
    assert len(ex3.variant_hints) == 1
    assert ex3.variant_hints[0].startswith("[t-2-r-2] column 'Resist film thickness (nm)' lists 2")
    assert not any("3/7" in h for h in ex3.variant_hints)


def test_render_separates_target_and_inherited_values(ex3):
    text = ex3.render(DOC)
    a, d = text.index("## A."), text.index("## D. Inherited procedure from Example 1")
    assert a < text.index("[t-2-r-2] Example 3 | 100/200") < d
    assert text.index("[p-0024]") > d  # Example 1's solids content only under 'inherited'
    assert "Examples 1 to 2" not in text and "Example 4 |" not in text
    assert "TARGET EXAMPLE: 'Example 3'" in text
    assert "Possible experimental variants detected" in text


# ----- other examples ---------------------------------------------------------


def test_chained_inheritance_for_comparative_example():
    ctx = build_example_context(DOC, None, "Comparative Example 1")
    assert [lbl for lbl, _ in ctx.inherited_from] == ["Example 2", "Example 1"]
    assert "t-1-r-4" in ids(ctx, "tables") and "t-2-r-2" not in ctx.block_ids()


def test_unlabelled_row_below_belongs_to_the_example_above():
    ctx = build_example_context(DOC, None, "Example 5")
    assert ids(ctx, "tables")[-2:] == ["t-2-r-4", "t-2-r-5"]
    assert [lbl for lbl, _ in ctx.inherited_from] == ["Example 1"]


def test_unknown_label_falls_back_to_whole_document():
    ctx = build_example_context(DOC, None, "Example 99")
    assert ctx.fallback and "whole document follows" in ctx.render(DOC)
    assert build_example_context(DOC, None, "Embodiment A").fallback


def test_examples_as_columns_and_merged_rows_in_html_fixture():
    ctx = build_example_context(HTML_DOC, None, "Example 2")
    assert ids(ctx, "own") == ["h-0005", "p-0052"]
    assert [lbl for lbl, _ in ctx.inherited_from] == ["Example 1"]
    assert ids(ctx, "inherited") == ["h-0004", "p-0050", "p-0051"]
    tables = ids(ctx, "tables")
    # Table 1 has examples as columns -> whole table; Table 2 row of Example 2;
    # Table 3 merged row 'Examples 1 to 2' with its merged header
    assert {"t-1-r-3", "t-1-r-7"} <= set(tables)
    assert "t-2-r-3" in tables and "t-2-r-2" not in tables
    assert {"t-3-r-1-2", "t-3-r-3-4"} <= set(tables) and "t-3-r-3" not in tables
    assert {"p-0041", "p-0042"} <= set(ids(ctx, "definitions"))  # Synthesis Example 1
