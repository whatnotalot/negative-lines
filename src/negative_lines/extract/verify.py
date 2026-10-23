"""Check that every cited quote is actually in the cited block.

Status per reference:

- ``ok``: the quote occurs in the cited block
- ``ok_merged``: the quote occurs in the merged row that the cited physical row belongs
  to, or in one of the physical rows of a cited merged row
- ``elsewhere``: not in the cited block, but in other block(s) (``found_in``)
- ``not_found``: the quote does not occur anywhere (not verbatim / invented)
- ``unknown_block``: the cited block ID does not exist

Comparison is on normalized text (Unicode NFKC, case-folded, whitespace collapsed,
table cell separators ``|`` treated as spaces). Failed checks become record
warnings; they do not reject the record (no repair is triggered).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from negative_lines.ingest.document import Block, SourceDocument
from negative_lines.schema.llm import LLMRecord
from negative_lines.schema.refs import SourceRef

RefStatus = Literal["ok", "ok_merged", "elsewhere", "not_found", "unknown_block"]
VERIFIED = ("ok", "ok_merged")


@dataclass(frozen=True)
class RefCheck:
    where: str
    block_id: str
    purpose: str
    status: RefStatus
    found_in: tuple[str, ...] = ()

    @property
    def verified(self) -> bool:
        return self.status in VERIFIED


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).casefold().replace("|", " ")
    return re.sub(r"\s+", " ", t).strip()


class QuoteIndex:
    def __init__(self, doc: SourceDocument):
        self.blocks: dict[str, Block] = {b.block_id: b for b in doc.blocks}
        self.text: dict[str, str] = {k: normalize(b.text) for k, b in self.blocks.items()}

    def related(self, block: Block) -> list[str]:
        out = []
        if block.merged_into:
            out.append(block.merged_into)
        if block.source_rows:
            out.extend(block.source_rows)
        return out

    def find(self, quote: str, limit: int = 5) -> tuple[str, ...]:
        hits = [k for k, t in self.text.items() if quote in t]
        # prefer merged rows over their physical rows when both match
        merged = {k for k in hits if self.blocks[k].kind == "table_row_merged"}
        hits = [k for k in hits if self.blocks[k].merged_into not in merged]
        return tuple(hits[:limit])

    def check(self, ref: SourceRef, where: str) -> RefCheck:
        q = normalize(ref.quote)
        block = self.blocks.get(ref.block_id)
        if not q:
            return RefCheck(where, ref.block_id, ref.purpose, "not_found")
        if block is None:
            return RefCheck(where, ref.block_id, ref.purpose, "unknown_block", self.find(q))
        if q in self.text[ref.block_id]:
            return RefCheck(where, ref.block_id, ref.purpose, "ok")
        if any(q in self.text[r] for r in self.related(block) if r in self.text):
            return RefCheck(where, ref.block_id, ref.purpose, "ok_merged")
        found = self.find(q)
        return RefCheck(where, ref.block_id, ref.purpose, "elsewhere" if found else "not_found",
                        found)  # fmt: skip


def check_record(rec: LLMRecord, doc: SourceDocument | QuoteIndex) -> list[RefCheck]:
    idx = doc if isinstance(doc, QuoteIndex) else QuoteIndex(doc)
    out = [idx.check(r, "record") for r in rec.refs]
    for i, c in enumerate(rec.components):
        out += [idx.check(r, f"components[{i}] {c.name_as_written}") for r in c.refs]
    for name in ("coating", "softbake", "exposure", "peb", "development", "hardbake"):
        group = getattr(rec.process, name)
        if group is not None:
            out += [idx.check(r, f"process.{name}") for r in group.refs]
    for i, x in enumerate(rec.results):
        out += [idx.check(r, f"results[{i}] {x.metric}") for r in x.refs]
    return out


def warnings_from(checks: list[RefCheck]) -> list[str]:
    msgs = []
    for c in checks:
        if c.verified:
            continue
        if c.status == "elsewhere":
            msgs.append(f"ref {c.where} -> {c.block_id}: quote is not in the cited block "
                        f"(found in {', '.join(c.found_in)})")  # fmt: skip
        elif c.status == "not_found":
            msgs.append(f"ref {c.where} -> {c.block_id}: quote not found in the document")
        else:
            msgs.append(f"ref {c.where}: unknown block {c.block_id}")
    return msgs


def summarize(checks: list[RefCheck]) -> dict[str, int]:
    counts = Counter(c.status for c in checks)
    return {
        "total": len(checks),
        "verified": sum(counts[s] for s in VERIFIED),
        **{
            s: counts.get(s, 0)
            for s in ("ok", "ok_merged", "elsewhere", "not_found", "unknown_block")
        },
    }
