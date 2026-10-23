"""One-call extraction API: ``list_examples`` and ``extract_patent``.

Typical use::

    from negative_lines.extract.api import list_examples, extract_patent

    labels = list_examples("US20080241753A1")                 # ingest + 1 map call
    run = extract_patent("US20080241753A1", examples=["Example 3", "Example 4"])
    run.records        # list[FormulationRecord] (vocab v3)
    run.failures       # examples still invalid after the repair retry
    run.paths          # files written under data/extracted/<doc_id>/<run_id>/

Rules:

- Documents are checked against ``eval/split.yaml``. Benchmark documents are
  refused unless ``allow_benchmark=True`` (approved milestone runs only).
  Documents not in the split (new patents for the dataset) are allowed.
- ``examples=None`` extracts every example in the document map; ``max_examples``
  is an optional cap (an error, not a silent truncation, if exceeded).
- LLM responses are cached in ``data/cache/`` (re-runs cost nothing); a cached
  document map makes ``list_examples`` followed by ``extract_patent`` cost
  only the per-example calls.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from negative_lines import __version__
from negative_lines.config import LLMProfile, get_settings, load_llm_profile
from negative_lines.extract import prompts
from negative_lines.extract.pipeline import PipelineResult, run_document
from negative_lines.extract.verify import summarize
from negative_lines.gold.split import BenchmarkAccessError, get_split
from negative_lines.ingest.document import SourceDocument
from negative_lines.llm import CallResult, JsonCache, StructuredCaller, build_chat_model
from negative_lines.schema.enums import VOCAB_VERSION
from negative_lines.schema.llm import DocumentMap
from negative_lines.schema.record import FormulationRecord

DEFAULT = object()  # sentinel: "use the configured default"


class TooManyExamplesError(ValueError):
    pass


@dataclass
class ExtractionRun:
    run_id: str
    doc: SourceDocument
    profile: LLMProfile
    result: PipelineResult
    split_set: str | None
    notes: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    paths: dict[str, Path] = field(default_factory=dict)

    @property
    def records(self) -> list[FormulationRecord]:
        return self.result.records

    @property
    def failures(self):
        return self.result.failures

    @property
    def document_map(self) -> DocumentMap | None:
        return self.result.map_call.parsed

    def calls(self) -> list[CallResult]:
        return [self.result.map_call, *(e.call for e in self.result.examples)]

    def usage(self) -> dict[str, int]:
        """Token totals; cached calls are counted separately (they cost nothing now)."""
        tot = {"calls": 0, "cached_calls": 0, "attempts": 0, "input_tokens": 0,
               "output_tokens": 0, "cached_input_tokens": 0, "cached_output_tokens": 0}  # fmt: skip
        for c in self.calls():
            tot["calls"] += 1
            tot["attempts"] += c.attempts
            prefix = "cached_" if c.cached else ""
            tot["cached_calls"] += int(c.cached)
            for u in c.usage:
                tot[f"{prefix}input_tokens"] += int(u.get("input_tokens", 0))
                tot[f"{prefix}output_tokens"] += int(u.get("output_tokens", 0))
        return tot

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "doc_id": self.doc.doc_id,
            "url": self.doc.url,
            "split_set": self.split_set,
            "profile": self.profile.name,
            "model": f"{self.profile.provider}:{self.profile.model}",
            "prompt_version": prompts.PROMPT_VERSION,
            "vocab_version": VOCAB_VERSION,
            "package_version": __version__,
            "created_utc": self.run_id.split("_")[0],
            "duration_s": round(self.duration_s, 1),
            "examples_in_map": [e.label for e in self.document_map.examples]
            if self.document_map
            else [],
            "examples_requested": [e.label for e in self.result.examples],
            "records": len(self.records),
            "failed_examples": [f.label for f in self.failures],
            "ref_checks": summarize([c for e in self.result.examples for c in e.ref_checks]),
            "per_example": [
                {
                    "example": e.label,
                    "valid": e.call.ok,
                    "attempts": e.call.attempts,
                    "repair_errors": e.call.error_history,
                    "records": [r.record_id for r in e.records],
                    "ref_checks": e.ref_summary(),
                    "context": {
                        "blocks": len(e.context.block_ids()),
                        "fallback": e.context.fallback,
                        "inherited_from": [lbl for lbl, _ in e.context.inherited_from],
                        "variant_hints": e.context.variant_hints,
                        "notes": e.context.notes,
                    }
                    if e.context
                    else None,
                }
                for e in self.result.examples
            ],
            "map_ok": self.result.map_call.ok,
            "usage": self.usage(),
            "warnings": self.result.warnings,
            "notes": self.notes,
        }


# ----- helpers ------------------------------------------------------------


def _check_split(doc_id: str, allow_benchmark: bool) -> tuple[str | None, list[str]]:
    split = get_split()
    set_name = split.set_of(doc_id)
    notes: list[str] = []
    if set_name == "benchmark" and not allow_benchmark:
        raise BenchmarkAccessError(
            f"{doc_id} is a reserved benchmark document (eval/split.yaml); "
            "extract it only for an approved milestone run with allow_benchmark=True"
        )
    if set_name is None:
        notes.append(f"{doc_id} is not in eval/split.yaml (not a gold document)")
    for d in split.docs:
        if d.doc_id == doc_id and d.extraction and d.extraction != "html":
            notes.append(f"split.yaml marks extraction for {doc_id} as {d.extraction!r}")
    return set_name, notes


def _document(doc_or_id: str | SourceDocument) -> SourceDocument:
    if isinstance(doc_or_id, SourceDocument):
        return doc_or_id
    from negative_lines.ingest.google_patents import ingest_google_patent

    return ingest_google_patent(doc_or_id)


def _caller(
    profile: str | LLMProfile | None, llm: Any, use_cache: bool, max_repairs: int
) -> StructuredCaller:
    prof = profile if isinstance(profile, LLMProfile) else load_llm_profile(profile)
    return StructuredCaller(
        llm if llm is not None else build_chat_model(prof),
        prof,
        cache=JsonCache(get_settings().cache_dir) if use_cache else None,
        max_repairs=max_repairs,
        prompt_version=prompts.PROMPT_VERSION,
    )


def _write(run: ExtractionRun, out_dir: Path) -> dict[str, Path]:
    d = out_dir / run.doc.doc_id / run.run_id
    d.mkdir(parents=True, exist_ok=True)
    paths = {
        "records": d / "records.jsonl",
        "document_map": d / "document_map.json",
        "failures": d / "failures.json",
        "run": d / "run.json",
    }
    with paths["records"].open("w", encoding="utf-8") as fh:
        for rec in run.records:
            fh.write(rec.model_dump_json() + "\n")
    dm = run.result.map_call
    paths["document_map"].write_text(
        json.dumps(
            dm.raw if dm.raw is not None else {"errors": dm.errors}, indent=2, ensure_ascii=False
        ),  # fmt: skip
        encoding="utf-8",
    )
    failures = [
        {
            "example": f.label,
            "attempts": f.call.attempts,
            "errors": f.call.errors,
            "error_history": f.call.error_history,
            "raw": f.call.raw,
        }
        for f in run.failures
    ]
    if not dm.ok:
        failures.insert(0, {"example": "<document map>", "attempts": dm.attempts,
                            "errors": dm.errors, "error_history": dm.error_history,
                            "raw": dm.raw})  # fmt: skip
    paths["failures"].write_text(json.dumps(failures, indent=2, ensure_ascii=False), "utf-8")
    paths["run"].write_text(json.dumps(run.summary(), indent=2, ensure_ascii=False), "utf-8")
    return paths


# ----- public API -----------------------------------------------------------


def list_examples(
    doc_or_id: str | SourceDocument,
    *,
    profile: str | LLMProfile | None = None,
    use_cache: bool = True,
    allow_benchmark: bool = False,
    llm: Any = None,
) -> list[tuple[str, bool]]:
    """(label, is_comparative) of every example, from one document-map call."""
    doc = _document(doc_or_id)
    _check_split(doc.doc_id, allow_benchmark)
    caller = _caller(profile, llm, use_cache, max_repairs=1)
    call = caller.call(DocumentMap, prompts.map_messages(doc.render()), name=f"{doc.doc_id}:map")
    if not call.ok:
        raise RuntimeError(f"document map failed: {call.errors}")
    return [(e.label, e.is_comparative) for e in call.parsed.examples]


def extract_patent(
    doc_or_id: str | SourceDocument,
    *,
    examples: Sequence[str] | None = None,
    profile: str | LLMProfile | None = None,
    max_examples: int | None = None,
    use_cache: bool = True,
    allow_benchmark: bool = False,
    out_dir: Path | str | None | object = DEFAULT,
    max_repairs: int = 1,
    llm: Any = None,
) -> ExtractionRun:
    """Ingest (if given an ID), map, extract examples, enrich, and write the run.

    ``out_dir``: default ``data/extracted/``; ``None`` writes nothing.
    ``llm``: inject a chat model (tests); otherwise built from the profile.
    """
    t0 = time.perf_counter()
    doc = _document(doc_or_id)
    set_name, notes = _check_split(doc.doc_id, allow_benchmark)
    if max_examples is not None and examples is not None and len(examples) > max_examples:
        raise TooManyExamplesError(
            f"{len(examples)} examples requested, max_examples={max_examples}"
        )
    caller = _caller(profile, llm, use_cache, max_repairs)

    dmap = None
    if examples is None and max_examples is not None:
        # map first, then check the count before any per-example call; the map is reused
        dmap = caller.call(
            DocumentMap, prompts.map_messages(doc.render()), name=f"{doc.doc_id}:map"
        )
        if dmap.ok and len(dmap.parsed.examples) > max_examples:
            raise TooManyExamplesError(
                f"document map lists {len(dmap.parsed.examples)} examples, max_examples="
                f"{max_examples}; pass examples=[...] or raise max_examples"
            )

    result = run_document(doc, caller, examples=examples, map_call=dmap)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + f"_{caller.profile.name}"
    run = ExtractionRun(run_id=run_id, doc=doc, profile=caller.profile, result=result,
                        split_set=set_name, notes=notes)  # fmt: skip
    run.duration_s = time.perf_counter() - t0
    target = get_settings().extracted_dir if out_dir is DEFAULT else out_dir
    if target is not None:
        run.paths = _write(run, Path(target))
    return run
