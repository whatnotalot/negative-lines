"""Per-example context assembly.

Instead of the whole document, each example call receives only the blocks that matter
for that example, grouped so the model can tell example-specific values from inherited
or shared information. Block IDs are preserved; the model cites them as before.

Groups (in prompt order):

A ``own``          text of the section(s) whose heading names the example
                   ("Example 3", "Examples 3 to 24 and Comparative Example 1")
B ``tables``       table captions, header rows and the rows labelled with the example
                   (whole table if examples are columns, or if an unlabelled table sits in
                   the example's own section); unlabelled rows directly below an example's
                   row (e.g. a second variant row) belong to it
C ``mentions``     other paragraphs that name the example ("In Examples 3, 5 and 7 ...")
D ``inherited``    sections of examples the target explicitly refers to ("the same method
                   as that used in Example 1"), followed recursively (depth 2)
E ``definitions``  Synthesis-Example sections referenced by A-D, codename definitions from
                   the document map, and paragraphs that define codenames used in A-C
                   ("PAG1 denotes ...")
F ``shared``       shared conditions and grade legends from the document map that apply

Each block appears once, in the first group that claims it. If neither A nor B finds
anything, the whole document is used (``fallback``).

All rules are deterministic text rules (example-label parsing in ``extract.labels``);
nothing here is specific to one patent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from negative_lines.extract.labels import (
    Key,
    find_refs,
    heading_keys,
    is_example_key,
    keys_in,
    label_key,
)
from negative_lines.ingest.document import Block, SourceDocument
from negative_lines.schema.llm import DocumentMap

GROUP_TITLES = {
    "own": "A. Text of the section(s) for the target example",
    "tables": "B. Table rows for the target example (with table captions and header rows)",
    "mentions": "C. Other passages that mention the target example",
    "inherited": "D. Inherited procedure",
    "definitions": "E. Definitions of ingredients and codenames",
    "shared": "F. Conditions or grade legends stated for several examples",
}
MAX_DEPTH = 2
MAX_DEFINITION_BLOCKS = 10

SAME_AS = re.compile(
    r"\bsame\s+(?:method|manner|procedure|conditions?|way|process|operations?)\b[^.;]{0,80}?"
    r"\b(?:as|to)\b[^.;]{0,40}?(?P<ref>(?:comparative\s+)?(?:examples?|embodiments?)\s+"
    r"\d+(?:-\d+)?)"
    r"|\b(?:method|procedure)\s+(?:of|described\s+in)\s+(?P<ref2>(?:comparative\s+)?"
    r"(?:examples?|embodiments?)\s+\d+(?:-\d+)?)",
    re.IGNORECASE,
)
DEFINITION_CUE = re.compile(
    r"\b(?:denotes?|represents?|refers?\s+to|is\s+referred\s+to\s+as|means|stands\s+for|"
    r"abbreviated)\b",
    re.IGNORECASE,
)
CODENAME = re.compile(
    r"\b[A-Z][A-Za-z]{0,5}-?\d{1,3}[a-z]?\b"  # PAG1, X1, B-1, Q-1
    r"|\b(?:Resin|Polymer|Copolymer|Compound|Crosslinker)\s+[A-Z0-9][\w-]*"  # Resin 1
    r"|\bChemical\s+Formula\s+\(\d+\)"  # Chemical Formula (2)
    r"|\b[A-Z]{2,5}\b"  # PM, PE, PGMEA (only taken from table cells)
)
MULTI_VALUE = re.compile(r"^\s*\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)+\s*$")
CONDITION_WORDS = re.compile(
    r"thickness|dose|temperature|temp\b|time|energy|intensity|exposure|bake|pab|peb|"
    r"\bnm\b|µm|\bum\b|mj|°\s*c|\bsec\b|\bkv\b",
    re.IGNORECASE,
)
TEXT_VARIANTS = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(nm|µm|um|mJ/cm2|°\s*C)\s*(?:,|or|and)\s*(\d+(?:\.\d+)?)\s*\2",
    re.IGNORECASE,
)


@dataclass
class Section:
    heading: Block | None
    keys: set[Key]
    blocks: list[Block] = field(default_factory=list)  # heading first, then its blocks


@dataclass
class ExampleContext:
    label: str
    key: Key | None
    groups: dict[str, list[Block]]
    inherited_from: list[tuple[str, str]] = field(default_factory=list)  # (label, evidence)
    variant_hints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    fallback: bool = False

    def block_ids(self) -> list[str]:
        return [b.block_id for g in self.groups.values() for b in g]

    def render(self, doc: SourceDocument) -> str:
        head = [
            f"[doc_id: {doc.doc_id}] [source_type: {doc.source_type}]",
            f"Title: {doc.title or '-'} | Assignee/authors: {doc.assignee_or_authors or '-'} "
            f"| Year: {doc.year or '-'} | Language: {doc.language or '-'}",
            "",
            f"TARGET EXAMPLE: {self.label!r}",
        ]
        if self.fallback:
            head.append("NOTE: no section or table row could be located for this example; the "
                        "whole document follows.")  # fmt: skip
            return "\n".join(head) + "\n\n" + doc.render().split("\n", 3)[-1]
        lines = head
        for name, blocks in self.groups.items():
            if not blocks:
                continue
            title = GROUP_TITLES[name]
            if name == "inherited" and self.inherited_from:
                srcs = "; ".join(f"{lbl} (because: {ev})" for lbl, ev in self.inherited_from)
                title += f" from {srcs}"
            lines += ["", f"## {title}"]
            lines += [_line(b) for b in blocks]
        if self.variant_hints:
            lines += ["", "## Possible experimental variants detected (check before deciding "
                          "how many records to create)"]  # fmt: skip
            lines += [f"- {h}" for h in self.variant_hints]
        return "\n".join(lines)


def _line(b: Block) -> str:
    return f"[{b.block_id}] {'## ' if b.kind == 'heading' else ''}{b.text}"


def _is_major(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) >= 0.8


def sections(doc: SourceDocument) -> list[Section]:
    """Description split at example/synthesis headings and at major (upper-case) headings."""
    out: list[Section] = [Section(None, set())]
    for b in doc.blocks:
        if b.section != "description":
            continue
        if b.kind == "heading":
            keys = heading_keys(b.text)
            if keys or _is_major(b.text):
                out.append(Section(b, keys, [b]))
                continue
        out[-1].blocks.append(b)
    return out


def _visible_rows(doc: SourceDocument, table_id: str) -> list[Block]:
    return [b for b in doc.blocks if b.table_id == table_id and b.kind in ("table_row", "table_row_merged")
            and b.merged_into is None]  # fmt: skip


def _row_keys(row: Block) -> set[Key]:
    first = (row.cells or [""])[0]
    refs = find_refs(first)
    return {k for k, start, _ in refs if is_example_key(k) and start <= 2}


def _table_rows(doc: SourceDocument, key: Key, own_ids: set[str]) -> tuple[list[Block], list[str]]:
    """Blocks of every table that concerns ``key`` and variant hints from its rows."""
    out: list[Block] = []
    hints: list[str] = []
    for tid in dict.fromkeys(b.table_id for b in doc.blocks if b.table_id):
        caption = [b for b in doc.blocks if b.table_id == tid and b.kind == "table_caption"]
        rows = _visible_rows(doc, tid)
        labelled = [i for i, r in enumerate(rows) if _row_keys(r)]
        if labelled:  # examples are rows
            header = rows[: labelled[0]]
            mine: list[Block] = []
            for i in labelled:
                if key in _row_keys(rows[i]):
                    mine.append(rows[i])
                    j = i + 1  # unlabelled rows directly below belong to this row
                    while j < len(rows) and j not in labelled and not (rows[j].cells or [""])[0]:
                        mine.append(rows[j])
                        j += 1
            if mine:
                out += caption + header + mine
                hints += _variant_hints(tid, header, mine)
            continue
        column_keys = {k for r in rows for c in (r.cells or [])[1:] for k in keys_in(c)}
        in_own = any(r.block_id in own_ids for r in rows) or any(
            c.block_id in own_ids for c in caption
        )
        if key in column_keys or (in_own and not column_keys):
            out += caption + rows
    return out, hints


def _variant_hints(tid: str, header: list[Block], rows: list[Block]) -> list[str]:
    width = max((len(r.cells or []) for r in header + rows), default=0)
    head = [" ".join((h.cells or [""] * width)[j] if j < len(h.cells or []) else "" for h in header).strip()
            for j in range(width)]  # fmt: skip
    hints = []
    for r in rows:
        for j, cell in enumerate(r.cells or []):
            if j < len(head) and MULTI_VALUE.match(cell) and CONDITION_WORDS.search(head[j]):
                n = cell.count("/") + 1
                hints.append(f"[{r.block_id}] column '{head[j]}' lists {n} values '{cell.strip()}': "
                             "if results are reported for each value, create one record per value")  # fmt: skip
    return hints


def _inherits(blocks: list[Block], key: Key, own_ids: set[str]) -> list[tuple[Key, str]]:
    """Examples that ``key`` explicitly refers to as the source of its procedure."""
    out: list[tuple[Key, str]] = []
    for b in blocks:
        for sentence in re.split(r"(?<=[.;])\s+", b.text):
            for m in SAME_AS.finditer(sentence):
                ref_text = m.group("ref") or m.group("ref2")
                span = m.span("ref") if m.group("ref") else m.span("ref2")
                ref = label_key(ref_text)
                if ref is None or ref == key or not is_example_key(ref):
                    continue
                others = {k for k, s, e in find_refs(sentence)
                          if is_example_key(k) and not (s <= span[0] < e)}  # fmt: skip
                applies = key in others if others else b.block_id in own_ids
                if applies and ref not in [r for r, _ in out]:
                    evidence = f'[{b.block_id}] "{sentence.strip()[:160]}"'
                    out.append((ref, evidence))
    return out


def _codenames(text_blocks: list[Block], table_blocks: list[Block]) -> set[str]:
    names: set[str] = set()
    for b in table_blocks:
        for c in b.cells or []:
            names |= {m.group(0) for m in CODENAME.finditer(c)}
    for b in text_blocks:
        # from running text skip plain abbreviations (TMAH, PEB); keep X1, PAG1, Resin 1
        names |= {m.group(0) for m in CODENAME.finditer(b.text)
                  if not (m.group(0).isalpha() and m.group(0).isupper())}  # fmt: skip
    return {n for n in names if not re.fullmatch(r"[A-Z]?\d+", n)}


def _contains_word(text: str, word: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", text) is not None


def build_example_context(
    doc: SourceDocument, dmap: DocumentMap | None, label: str
) -> ExampleContext:
    key = label_key(label)
    groups: dict[str, list[Block]] = {g: [] for g in GROUP_TITLES}
    ctx = ExampleContext(label=label, key=key, groups=groups)
    if key is None:
        ctx.fallback = True
        ctx.notes.append(f"label {label!r} is not an example reference")
        return ctx
    secs = sections(doc)
    by_id = {b.block_id: b for b in doc.blocks}
    taken: set[str] = set()

    def add(group: str, blocks: list[Block]) -> None:
        for b in blocks:
            if b.block_id not in taken:
                taken.add(b.block_id)
                groups[group].append(b)

    def text_blocks(sec_list: list[Section]) -> list[Block]:
        return [b for s in sec_list for b in s.blocks if b.kind not in ("table_row", "table_row_merged",
                "table_caption")]  # fmt: skip

    own_secs = [s for s in secs if key in s.keys]
    own_all_ids = {b.block_id for s in own_secs for b in s.blocks}
    add("own", text_blocks(own_secs))
    table_blocks, hints = _table_rows(doc, key, own_all_ids)
    add("tables", table_blocks)
    ctx.variant_hints = hints

    mention_blocks = [b for b in doc.blocks if b.section == "description" and b.kind in ("paragraph", "list_item")
                      and b.block_id not in own_all_ids and key in keys_in(b.text)]  # fmt: skip
    add("mentions", mention_blocks)
    for b in groups["own"]:
        for m in TEXT_VARIANTS.finditer(b.text):
            ctx.variant_hints.append(f"[{b.block_id}] text names several values '{m.group(0)}'")

    if not groups["own"] and not groups["tables"]:
        ctx.fallback = True
        ctx.notes.append("no section heading or table row names this example")
        return ctx

    # D: inherited procedures (explicit references only), recursively
    frontier: list[tuple[Key, list[Block], set[str]]] = [
        (key, groups["own"] + groups["mentions"], own_all_ids)
    ]
    seen = {key}
    for _depth in range(MAX_DEPTH):
        nxt = []
        for k, blocks, owned in frontier:
            for ref, evidence in _inherits(blocks, k, owned):
                if ref in seen:
                    continue
                seen.add(ref)
                ref_secs = [s for s in secs if s.keys == {ref}] or [
                    s for s in secs if ref in s.keys
                ]
                ref_blocks = text_blocks(ref_secs)
                if not ref_blocks:
                    ctx.notes.append(f"inherited example {ref} has no section of its own")
                    continue
                label_txt = ("Comparative Example " if ref[0] == "cex" else "Example ") + ref[1]
                ctx.inherited_from.append((label_txt, evidence))
                add("inherited", ref_blocks)
                nxt.append((ref, ref_blocks, {b.block_id for s in ref_secs for b in s.blocks}))
        frontier = nxt

    # E: definitions
    used_text = groups["own"] + groups["mentions"] + groups["inherited"]
    syn_keys = {k for b in used_text + groups["tables"] for k in keys_in(b.text) if k[0] == "syn"}
    add("definitions", text_blocks([s for s in secs if s.keys & syn_keys]))
    names = _codenames(groups["own"] + groups["inherited"], groups["tables"])
    if dmap is not None:
        for d in dmap.codename_definitions:
            if any(
                _contains_word(n, d.codename) or _contains_word(d.codename, n) for n in names
            ) or any(_contains_word(b.text, d.codename) for b in used_text + groups["tables"]):
                add("definitions", [by_id[r.block_id] for r in d.refs if r.block_id in by_id])
    cue_hits = []
    for b in doc.blocks:
        if (
            b.section != "description"
            or b.kind not in ("paragraph", "list_item")
            or b.block_id in taken
        ):
            continue
        if DEFINITION_CUE.search(b.text) and any(_contains_word(b.text, n) for n in names):
            cue_hits.append(b)
    add("definitions", cue_hits[:MAX_DEFINITION_BLOCKS])

    # F: shared conditions and grade legends from the document map
    if dmap is not None:
        for s in dmap.shared_conditions:
            applies = {a.strip().lower() for a in s.applies_to}
            if (
                "all" in applies
                or label.lower() in applies
                or any(key in keys_in(a) for a in s.applies_to)
            ):
                add("shared", [by_id[r.block_id] for r in s.refs if r.block_id in by_id])
        for g in dmap.grade_scales:
            add("shared", [by_id[r.block_id] for r in g.refs if r.block_id in by_id])
    for g in groups.values():
        g.sort(key=lambda b: doc.blocks.index(b))
    return ctx
