"""Read ``eval/split.yaml`` (the authoritative document-level split)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from negative_lines.config import REPO_ROOT

SPLIT_PATH = REPO_ROOT / "eval" / "split.yaml"


class BenchmarkAccessError(PermissionError):
    """A benchmark document was requested without explicit permission."""


@dataclass(frozen=True)
class SplitDoc:
    no: str
    doc_id: str
    records: int
    set: str
    extraction: str | None
    note: str | None


@dataclass(frozen=True)
class Split:
    raw: dict
    docs: tuple[SplitDoc, ...]

    @property
    def gold_version(self) -> str:
        return str(self.raw["gold_version"])

    def doc_ids(self, set_name: str) -> tuple[str, ...]:
        return tuple(d.doc_id for d in self.docs if d.set == set_name)

    def set_of(self, doc_id: str) -> str | None:
        for d in self.docs:
            if d.doc_id == doc_id:
                return d.set
        return None


def load_split(path: Path | str = SPLIT_PATH) -> Split:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    docs = []
    for set_name, spec in raw["sets"].items():
        for d in spec["documents"]:
            docs.append(
                SplitDoc(
                    no=str(d["num"]),  # 'no' would be parsed as boolean False in YAML 1.1
                    doc_id=d["doc_id"],
                    records=int(d["records"]),
                    set=set_name,
                    extraction=d.get("extraction"),
                    note=d.get("note"),
                )
            )
    return Split(raw=raw, docs=tuple(docs))


@lru_cache(maxsize=1)
def get_split() -> Split:
    return load_split()


def doc_id_patterns(doc_id: str) -> list[str]:
    """Strings that identify a document: the full id and the id without kind code.

    ``US7432034B2`` -> ``US7432034B2``, ``US7432034`` (file names often drop the kind code).
    """
    pats = [doc_id]
    m = re.match(r"^([A-Z]{2}\d+)[A-Z]\d?$", doc_id)
    if m:
        pats.append(m.group(1))
    return pats
