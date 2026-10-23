"""Small synthetic SourceDocuments for context-assembly tests (no real patent text).

``range_section_doc`` mirrors the structures that broke the first real run:
range headings ("Examples 3 to 4 and Comparative Example 1"), a sentence that assigns
procedures to examples ("In Examples 3 and 5, the same method as that used in Example 1
was used"), formulation rows labelled "Examples 3 to 4", a conditions table with
thickness pairs "100/200", codename definitions, an inherited Example 1 procedure that
contains Example-1-specific values (50/100 nm, solids 3.5 %), and an underlayer.
"""

from __future__ import annotations

from negative_lines.ingest.document import Block, SourceDocument


def _p(bid: str, text: str, kind: str = "paragraph") -> Block:
    loc = f"[{bid[2:]}]" if bid.startswith("p-") else text
    return Block(block_id=bid, kind=kind, section="description", location=loc, text=text)


def _h(bid: str, text: str) -> Block:
    return Block(block_id=bid, kind="heading", section="description", location=text, text=text)


def _row(tid: str, i: int, cells: list[str]) -> Block:
    return Block(block_id=f"{tid}-r-{i}", kind="table_row", section="description",
                 location=f"Table {tid[2:]}, row {i}", text=" | ".join(cells), table_id=tid,
                 row_index=i, cells=cells)  # fmt: skip


def _cap(tid: str) -> Block:
    return Block(block_id=f"{tid}-cap", kind="table_caption", section="description",
                 location=f"Table {tid[2:]}", text=f"TABLE {tid[2:]}", table_id=tid)  # fmt: skip


def range_section_doc() -> SourceDocument:
    blocks = [
        _h("h-0001", "BACKGROUND ART"),
        _p("p-0001", "Negative resists are used for fine patterns."),
        _h("h-0010", "EXAMPLES"),
        _h("h-0011", "Synthesis Example 1"),
        _p("p-0010", "A copolymer of hydroxybenzylsilsesquioxane and phenylsilsesquioxane "
                     "(70/30 mol %) with Mw 10,000 was obtained; it is referred to as resin (X1)."),
        _h("h-0012", "Example 1"),
        _h("h-0013", "Two-Layer Resist Method"),
        _p("p-0020", "As the component (A), 100 parts by weight of the resin (X1) obtained in "
                     "Synthesis Example 1 was used."),
        _p("p-0021", "On a silicon substrate a novolak underlayer was baked at 230° C. for 90 "
                     "seconds to a thickness of 420 nm."),
        _p("p-0022", "The resist was baked at 90° C. for 90 seconds; two kinds of resist layers "
                     "having a thickness of 50 nm or 100 nm were produced, and written with an "
                     "electron beam writer set at an acceleration voltage of 70 kV."),
        _p("p-0023", "After exposure the layer was baked at 110° C. for 90 seconds and developed "
                     "with 2.38% by weight TMAH at 23° C. for 60 seconds."),
        _p("p-0024", "In case of the thickness of 50 nm and 100 nm, the solid content was "
                     "adjusted to 3.5% by weight and 5% by weight."),
        _h("h-0014", "Example 2"),
        _p("p-0030", "In the same manner as in Example 1 except that no underlayer was used, a "
                     "single-layer resist pattern was formed on an HMDS-treated substrate."),
        _h("h-0015", "Examples 3 to 5 and Comparative Example 1"),
        _p("p-0040", "As shown in Table 1, compositions were prepared. In Examples 3 and 5, the "
                     "same method as that used in Example 1 was used. In Example 4 and "
                     "Comparative Example 1, the same method as that used in Example 2 was used."),
        _p("p-0041", "In Table 1, PAG1 denotes triphenylsulfonium triflate, PM denotes propylene "
                     "glycol monomethyl ether acetate and PE denotes propylene glycol monomethyl "
                     "ether."),
        _cap("t-1"),
        _row("t-1", 1, ["", "(A) Resin", "(B) Acid generator", "Organic solvent",
                        "(D) Nitrogen-containing organic compound"]),
        _row("t-1", 2, ["Examples 1 to 2", "Resin 1 (100 parts by weight)",
                        "PAG1 (10 parts by weight)", "PM", "Trioctylamine (0.8 parts by weight)"]),
        _row("t-1", 3, ["Examples 3 to 4", "Resin 1 (100 parts by weight)",
                        "PAG1 (10 parts by weight)", "PM/PE = 3/7",
                        "Trioctylamine (0.8 parts by weight)"]),
        _row("t-1", 4, ["Comparative Example 1", "Resin 2 (100 parts by weight)",
                        "PAG1 (10 parts by weight)", "PM/PE = 3/7",
                        "Trioctylamine (0.8 parts by weight)"]),
        _cap("t-2"),
        _row("t-2", 1, ["", "Resist film thickness (nm)", "PAB", "L/S"]),
        _row("t-2", 2, ["Example 3", "100/200", "90° C./90 sec", "50 nm"]),
        _row("t-2", 3, ["Example 4", "50/100", "90° C./90 sec", "50 nm"]),
        _row("t-2", 4, ["Example 5", "100", "90° C./90 sec", "60 nm"]),
        _row("t-2", 5, ["", "200", "90° C./90 sec", "65 nm"]),
        _h("h-0016", "INDUSTRIAL APPLICABILITY"),
        _p("p-0060", "The resist of Example 3 is suitable for magnetic heads."),
    ]  # fmt: skip
    return SourceDocument(doc_id="SYNTH-CTX-1", title="Synthetic range-section patent",
                          blocks=blocks)  # fmt: skip
