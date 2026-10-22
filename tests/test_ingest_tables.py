"""Wrapped-row grouping rules (negative_lines.ingest.tables).

Row data below is copied from the parsed Google Patents page of development patent 06
(US20080241753A1, Tables 1 and 2), plus synthetic edge cases.
"""

from __future__ import annotations

import pytest

from negative_lines.ingest.tables import (
    group_wrapped_rows,
    is_complete_value,
    is_unfinished,
    join_cell,
    merge_cells,
)

T1_HEADER = [
    ["", "", "", "", "", "(D) Nitrogen-", "(E) Organic"],
    ["", "", "(B) Acid", "(C) Crosslinking", "Organic", "containing", "carboxylic"],
    ["", "(A) Resin", "generator", "agent", "solvent", "organic compound", "acid"],
]
T1_EX3_4 = [
    ["Examples", "Resin 1", "PAG1 (10 parts", "Chemical Formula (2)", "PM/PE =", "Trioctylamine",
     "Salicylic acid"],
    ["3 to 4", "(100 parts", "by weight)", "(7.3 parts by", "3/7", "(0.8 parts by", "(0.32 parts by"],
    ["", "by weight)", "", "weight)", "", "weight)", "weight)"],
]  # fmt: skip
T2_EX3 = [
    ["Example 3", "8 inch silicon", "420 nm", "100/200", "90° C./90 sec", "110° C./90 sec", "50 nm",
     "70 nm"],
    ["", "wafer"],  # Google Patents omits the trailing empty cells
]  # fmt: skip


def test_patent06_table1_header_and_formulation_row():
    rows = T1_HEADER + T1_EX3_4
    assert group_wrapped_rows(rows) == [(0, 2), (3, 5)]
    assert merge_cells(T1_HEADER) == [
        "", "(A) Resin", "(B) Acid generator", "(C) Crosslinking agent", "Organic solvent",
        "(D) Nitrogen-containing organic compound", "(E) Organic carboxylic acid",
    ]  # fmt: skip
    assert merge_cells(T1_EX3_4) == [
        "Examples 3 to 4", "Resin 1 (100 parts by weight)", "PAG1 (10 parts by weight)",
        "Chemical Formula (2) (7.3 parts by weight)", "PM/PE = 3/7",
        "Trioctylamine (0.8 parts by weight)", "Salicylic acid (0.32 parts by weight)",
    ]  # fmt: skip


def test_patent06_table2_shorter_continuation_row():
    assert group_wrapped_rows(T2_EX3) == [(0, 1)]
    assert merge_cells(T2_EX3)[:2] == ["Example 3", "8 inch silicon wafer"]
    assert merge_cells(T2_EX3)[2:] == T2_EX3[0][2:]


def test_consecutive_logical_rows_stay_separate():
    rows = T1_EX3_4 + T1_EX3_4
    assert group_wrapped_rows(rows) == [(0, 2), (3, 5)]


@pytest.mark.parametrize(
    "rows",
    [
        # separate value rows whose label wraps: both rows complete
        [["Photoacid", "PAG-1", "3.0", "—"], ["generator", "PAG-2", "—", "5.0"]],
        # empty label but values in both rows (a second variant row)
        [["Example 1", "100", "50 nm"], ["", "200", "60 nm"]],
        # a longer row never continues a shorter one
        [["(parts by mass)"], ["", "", "Example 1"]],
        # plain data rows
        [["Example 1", "120", "1.5", "A"], ["Example 2", "95", "1.2", "A"]],
    ],
    ids=["wrapped_label_values", "variant_row", "longer_row", "data_rows"],
)
def test_rows_that_must_not_merge(rows):
    assert group_wrapped_rows(rows) == []


def test_group_size_is_capped():
    rows = [["x (a"]] + [[""]] * 10
    first = group_wrapped_rows(rows)[0]
    assert first == (0, 5)  # MAX_GROUP = 6 physical rows


@pytest.mark.parametrize(
    "cell,unfinished",
    [
        ("PAG1 (10 parts", True), ("(0.8 parts by", True), ("PM/PE =", True), ("90° C./", True),
        ("(D) Nitrogen-", True), ("Resin A", False), ("Resin 1 (100 parts by weight)", False),
        ("—", False), ("", False), ("Chemical Formula (2)", False),
    ],
)  # fmt: skip
def test_is_unfinished(cell, unfinished):
    assert is_unfinished(cell) is unfinished


@pytest.mark.parametrize(
    "cell,complete",
    [("120", True), ("50 nm", True), ("100/200", True), ("—", True), ("3.5 wt%", True),
     ("90° C./90 sec", False), ("wafer", False), ("Example 1", False)],
)  # fmt: skip
def test_is_complete_value(cell, complete):
    assert is_complete_value(cell) is complete


def test_join_cell():
    assert join_cell("(D) Nitrogen-", "containing") == "(D) Nitrogen-containing"
    assert join_cell("PAG-", "1") == "PAG- 1"
    assert join_cell("90° C./", "90 sec") == "90° C./90 sec"
    assert join_cell("PM/PE =", "3/7") == "PM/PE = 3/7"
    assert join_cell("", "wafer") == "wafer" and join_cell("8 inch", "") == "8 inch"
