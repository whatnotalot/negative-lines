"""Parsed source document: an ordered list of citable blocks.

Block IDs are what the LLM cites in ``SourceRef.block_id``; they must be
stable and as specific as possible (one paragraph, one table row).

Conventions (Google Patents HTML; see tests/fixtures/ingest/):

=================  ===================  ==========================================
kind               block_id             location
=================  ===================  ==========================================
abstract           ``abs-1``            ``Abstract``
heading            ``h-0007``           heading text
paragraph          ``p-0041``           ``[0041]`` (printed paragraph number)
paragraph (no #)   ``p-u003``           ``unnumbered paragraph 3``
list_item          ``li-0097``          ``[0097]``
table_caption      ``t-1-cap``          ``Table 1``
table_row          ``t-1-r-3``          ``Table 1, row 3``
table_row_merged   ``t-1-r-7-9``        ``Table 1, rows 7-9``
claim              ``c-1``              ``Claim 1``
=================  ===================  ==========================================

Table rows are numbered 1.. over all non-empty rows of one ``<tables>``
element, across the split ``<table>`` pieces Google Patents emits. Physical
rows keep their cells verbatim.

Printed tables often wrap one logical row over several physical rows
("PAG1 (10 parts" / "by weight)"). Such groups additionally get a
``table_row_merged`` block whose cells are the joined cell texts and whose
``source_rows`` lists the physical rows; each physical row points to it via
``merged_into``. The prompt shows the merged row in place of its physical rows
(``render``); citations of either form are accepted by quote verification.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from negative_lines.schema.enums import SourceType

BlockKind = Literal[
    "abstract",
    "heading",
    "paragraph",
    "list_item",
    "table_caption",
    "table_row",
    "table_row_merged",
    "claim",
]
Section = Literal["abstract", "description", "claims"]


class Block(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    block_id: str
    kind: BlockKind
    section: Section
    location: str
    text: str = Field(description="Whitespace-normalized text; table rows joined with ' | '")
    heading: str | None = Field(None, description="Nearest preceding heading in the description")
    table_id: str | None = None
    row_index: int | None = Field(None, description="physical row number (first row if merged)")
    cells: list[str] | None = None
    merged_into: str | None = Field(None, description="physical row: ID of its merged row")
    source_rows: list[str] | None = Field(None, description="merged row: its physical rows")


class SourceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    source_type: SourceType = "patent"
    title: str | None = None
    assignee_or_authors: str | None = None
    year: int | None = None
    language: str | None = None
    url: str | None = None
    blocks: list[Block] = Field(default_factory=list)

    def block(self, block_id: str) -> Block:
        for b in self.blocks:
            if b.block_id == block_id:
                return b
        raise KeyError(block_id)

    def render(self, *, sections: tuple[Section, ...] = ("abstract", "description")) -> str:
        """Prompt context: one line per block, prefixed with its citable ID.

        Physical table rows that belong to a merged row are replaced by the merged row.
        """
        head = [
            f"[doc_id: {self.doc_id}] [source_type: {self.source_type}]",
            f"Title: {self.title or '-'} | Assignee/authors: {self.assignee_or_authors or '-'} "
            f"| Year: {self.year or '-'} | Language: {self.language or '-'}",
            "",
        ]
        lines = [
            f"[{b.block_id}] {'## ' if b.kind == 'heading' else ''}{b.text}"
            for b in self.blocks
            if b.section in sections and b.merged_into is None
        ]
        return "\n".join(head + lines)
