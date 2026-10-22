"""Google Patents HTML -> ``SourceDocument`` with citable blocks.

Rules are specified (and tested) by ``tests/fixtures/ingest/expected_blocks.json``;
see ``negative_lines.ingest.document`` for the block-ID conventions. Summary:

- metadata: ``publicationNumber``; ``DC.title``; ``assigneeOriginal``; year of the
  ``DC.date`` meta without ``scheme`` (publication date); description ``lang``.
- text: whitespace collapsed; inline elements joined without spaces
  (``M<sub>w</sub>`` -> ``Mw``), block elements separated by one space.
- paragraphs: ``p-<num>`` from the printed number (``num`` attribute), not the
  off-by-one ``id``; unnumbered (or ``num="0000"``) -> ``p-u001``...; a wrapper that
  only holds ``<tables>`` yields table blocks; empty blocks (e.g. structure
  images) are skipped.
- tables: ``t-<n>``; all ``<table>`` pieces of one ``<tables>`` are one table; the
  first row whose only non-empty cell is ``TABLE <n>`` is the caption; empty rows
  dropped; physical rows verbatim; rows wrapped by printing additionally get a
  merged ``t-<n>-r-<a>-<b>`` block (rules in ``negative_lines.ingest.tables``).
- claims: one block per numbered claim, nested claim text joined.

Network access is separate (``fetch_google_patent``) so parsing stays
deterministic and testable offline.
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

from negative_lines.ingest.document import Block, SourceDocument
from negative_lines.ingest.tables import group_wrapped_rows, merge_cells

BLOCK_TAGS = {
    "div", "p", "li", "ul", "ol", "br", "heading", "table", "thead", "tbody", "tr", "td", "th",
    "tables", "patent-tables", "claim-statement", "section", "chemistry", "maths", "figure",
}  # fmt: skip
CAPTION = re.compile(r"^table\s*\d+[a-z]?$", re.I)
_WS = re.compile(r"\s+")


def normalize_ws(text: str) -> str:
    return _WS.sub(" ", text.replace("\xa0", " ")).strip()


def text_of(node: Tag | NavigableString) -> str:
    """Text with inline elements joined and block elements separated by spaces."""
    if isinstance(node, NavigableString):
        return "" if node.__class__.__name__ == "Comment" else str(node)
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, Tag):
            inner = text_of(child)
            parts.append(f" {inner} " if child.name in BLOCK_TAGS else inner)
        elif child.__class__.__name__ != "Comment":
            parts.append(str(child))
    return "".join(parts)


def _classes(tag: Tag) -> list[str]:
    c = tag.get("class") or []
    return c if isinstance(c, list) else str(c).split()


def _is_paragraph(tag: Tag) -> bool:
    return tag.name == "div" and any(
        c in ("description-paragraph", "description-line") for c in _classes(tag)
    )


class _Builder:
    def __init__(self) -> None:
        self.blocks: list[Block] = []
        self.heading: str | None = None
        self.unnumbered = 0

    def add(self, **kw) -> None:
        if kw["text"]:
            self.blocks.append(Block(**kw))

    # ----- description --------------------------------------------------

    def description(self, root: Tag) -> None:
        for child in root.children:
            if isinstance(child, Tag):
                self._walk(child)

    def _walk(self, tag: Tag) -> None:
        if tag.name == "heading":
            text = normalize_ws(text_of(tag))
            hid = (
                tag.get("id")
                or f"h-u{len([b for b in self.blocks if b.kind == 'heading']) + 1:03d}"
            )
            self.add(block_id=hid, kind="heading", section="description", location=text,
                     text=text)  # fmt: skip
            self.heading = text or self.heading
            return
        if tag.name == "tables":
            self._table(tag)
            return
        if _is_paragraph(tag):
            if tag.find("tables"):
                for t in tag.find_all("tables"):
                    self._table(t)
                return
            self._paragraph(tag, tag.get("num"))
            return
        if tag.name == "li" and tag.get("num") and not tag.find(_is_paragraph):
            num = str(tag["num"])
            self.add(block_id=f"li-{num}", kind="list_item", section="description",
                     location=f"[{num}]", text=normalize_ws(text_of(tag)),
                     heading=self.heading)  # fmt: skip
            return
        for child in tag.children:
            if isinstance(child, Tag):
                self._walk(child)

    def _paragraph(self, tag: Tag, num: str | None) -> None:
        text = normalize_ws(text_of(tag))
        if not text:
            return
        if num and num.strip("0"):
            bid, loc = f"p-{num}", f"[{num}]"
        else:
            self.unnumbered += 1
            bid, loc = f"p-u{self.unnumbered:03d}", f"unnumbered paragraph {self.unnumbered}"
        self.add(block_id=bid, kind="paragraph", section="description", location=loc, text=text,
                 heading=self.heading)  # fmt: skip

    def _table(self, tables: Tag) -> None:
        n = int(tables.get("num") or len({b.table_id for b in self.blocks if b.table_id}) + 1)
        tid, caption_done = f"t-{n}", False
        rows: list[list[str]] = []
        for tr in tables.find_all("tr"):
            cells = [normalize_ws(text_of(td)) for td in tr.find_all(["td", "th"], recursive=False)]
            filled = [c for c in cells if c]
            if not filled:
                continue
            if not caption_done and len(filled) == 1 and CAPTION.match(filled[0]):
                self.add(block_id=f"{tid}-cap", kind="table_caption", section="description",
                         location=f"Table {n}", text=filled[0], heading=self.heading,
                         table_id=tid)  # fmt: skip
                caption_done = True
                continue
            rows.append(cells)

        groups = {start: end for start, end in group_wrapped_rows(rows)}
        member_of = {i: s for s, e in groups.items() for i in range(s, e + 1)}
        for i, cells in enumerate(rows):
            idx = i + 1
            start = member_of.get(i)
            merged_id = f"{tid}-r-{start + 1}-{groups[start] + 1}" if start is not None else None
            self.add(block_id=f"{tid}-r-{idx}", kind="table_row", section="description",
                     location=f"Table {n}, row {idx}", text=" | ".join(cells),
                     heading=self.heading, table_id=tid, row_index=idx, cells=cells,
                     merged_into=merged_id)  # fmt: skip
            if start is not None and i == groups[start]:
                first, last = start + 1, i + 1
                merged = merge_cells(rows[start : i + 1])
                self.add(block_id=merged_id, kind="table_row_merged", section="description",
                         location=f"Table {n}, rows {first}-{last}", text=" | ".join(merged),
                         heading=self.heading, table_id=tid, row_index=first, cells=merged,
                         source_rows=[f"{tid}-r-{k}" for k in range(first, last + 1)])  # fmt: skip

    # ----- abstract / claims --------------------------------------------

    def abstract(self, section: Tag) -> None:
        parts = section.find_all("div", class_="abstract") or [section]
        texts = [t for p in parts if (t := normalize_ws(text_of(p)))]
        for i, text in enumerate(texts, start=1):
            self.add(block_id=f"abs-{i}", kind="abstract", section="abstract",
                     location="Abstract" if len(texts) == 1 else f"Abstract, part {i}",
                     text=text)  # fmt: skip

    def claims(self, section: Tag) -> None:
        for claim in section.find_all("div", attrs={"num": True}):
            if "claim" not in _classes(claim):
                continue
            n = int(str(claim["num"]))
            self.add(block_id=f"c-{n}", kind="claim", section="claims", location=f"Claim {n}",
                     text=normalize_ws(text_of(claim)))  # fmt: skip


def _meta(soup: BeautifulSoup, name: str, *, without_scheme: bool = False) -> str | None:
    for m in soup.find_all("meta", attrs={"name": name}):
        if without_scheme and m.get("scheme"):
            continue
        content = m.get("content")
        if content:
            return normalize_ws(content)
    return None


def _itemprop(soup: BeautifulSoup, prop: str) -> str | None:
    el = soup.find(attrs={"itemprop": prop})
    return normalize_ws(el.get_text()) if el else None


def parse_google_patent_html(html: str, *, url: str | None = None) -> SourceDocument:
    soup = BeautifulSoup(html, "html.parser")
    doc_id = _itemprop(soup, "publicationNumber")
    if not doc_id:
        raise ValueError("no itemprop=publicationNumber: not a Google Patents page?")
    date = _meta(soup, "DC.date", without_scheme=True)
    # container is <div class="description"> or <ul class="description"> depending on the office
    desc_root = soup.select_one('section[itemprop="description"] .description')
    lang_el = desc_root or soup.select_one('section[itemprop="abstract"] [lang]')
    language = (lang_el.get("lang") or "").lower() or None if lang_el else None

    b = _Builder()
    abstract = soup.select_one('section[itemprop="abstract"]')
    if abstract:
        b.abstract(abstract)
    if desc_root:
        b.description(desc_root)
    claims = soup.select_one('section[itemprop="claims"]')
    if claims:
        b.claims(claims)

    return SourceDocument(
        doc_id=doc_id,
        source_type="patent",
        title=_meta(soup, "DC.title"),
        assignee_or_authors=_itemprop(soup, "assigneeOriginal"),
        year=int(date[:4]) if date and date[:4].isdigit() else None,
        language=language,
        url=url,
        blocks=b.blocks,
    )


def google_patents_url(doc_id: str, lang: str = "en") -> str:
    return f"https://patents.google.com/patent/{doc_id}/{lang}"


def fetch_google_patent(doc_id: str, *, raw_dir: Path | None = None, timeout: float = 60.0) -> str:
    """Download (or reuse) the Google Patents page; raw HTML is cached in ``data/raw/``."""
    import httpx

    from negative_lines.config import get_settings

    raw_dir = raw_dir or get_settings().raw_dir
    path = Path(raw_dir) / "google_patents" / f"{doc_id}.html"
    if path.exists():
        return path.read_text(encoding="utf-8")
    resp = httpx.get(google_patents_url(doc_id), timeout=timeout, follow_redirects=True,
                     headers={"User-Agent": "negative-lines/0.1 (research)"})  # fmt: skip
    resp.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(resp.text, encoding="utf-8")
    return resp.text


def ingest_google_patent(doc_id: str, **kw) -> SourceDocument:
    return parse_google_patent_html(
        fetch_google_patent(doc_id, **kw), url=google_patents_url(doc_id)
    )
