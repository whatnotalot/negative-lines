"""Extraction pipeline: document map -> one call per example -> enriched records.

Every cited quote is checked against its cited block (``extract.verify``);
failures become record warnings and per-example ``ref_checks``.

The document map is built from the whole rendered document; each example call gets
only its per-example context (``extract.context``: own text, table rows, mentions,
inherited procedures, definitions, shared conditions) plus the relevant part of the map.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from negative_lines.enrich.convert import to_formulation_record
from negative_lines.enrich.ids import make_record_id, unique_id
from negative_lines.extract import prompts
from negative_lines.extract.context import ExampleContext, build_example_context
from negative_lines.extract.verify import (
    QuoteIndex,
    RefCheck,
    check_record,
    summarize,
    warnings_from,
)
from negative_lines.ingest.document import SourceDocument
from negative_lines.llm.structured import CallResult, StructuredCaller
from negative_lines.schema.llm import DocumentInfo, DocumentMap, ExampleExtraction
from negative_lines.schema.record import FormulationRecord


@dataclass
class ExampleOutcome:
    label: str
    call: CallResult[ExampleExtraction]
    records: list[FormulationRecord] = field(default_factory=list)
    ref_checks: list[RefCheck] = field(default_factory=list)
    context: ExampleContext | None = None

    def ref_summary(self) -> dict[str, int]:
        return summarize(self.ref_checks)


@dataclass
class PipelineResult:
    doc_id: str
    map_call: CallResult[DocumentMap]
    examples: list[ExampleOutcome] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def records(self) -> list[FormulationRecord]:
        return [r for ex in self.examples for r in ex.records]

    @property
    def failures(self) -> list[ExampleOutcome]:
        return [ex for ex in self.examples if not ex.call.ok]


def document_info(doc: SourceDocument, dmap: DocumentMap, warn: list[str]) -> DocumentInfo:
    """Ingested metadata wins (deterministic); the LLM's map only fills gaps."""
    llm = dmap.document
    if llm.doc_id.replace(" ", "") != doc.doc_id:
        warn.append(f"document map doc_id {llm.doc_id!r} differs from ingested {doc.doc_id!r}")
    return DocumentInfo(
        source_type=doc.source_type,
        doc_id=doc.doc_id,
        title=doc.title or llm.title,
        assignee_or_authors=doc.assignee_or_authors or llm.assignee_or_authors,
        year=doc.year or llm.year,
        language=doc.language or llm.language,
    )


def run_document(
    doc: SourceDocument,
    caller: StructuredCaller,
    *,
    examples: Sequence[str] | None = None,
    map_call: CallResult[DocumentMap] | None = None,
) -> PipelineResult:
    """Run map + per-example extraction. ``examples`` limits which labels are extracted.

    ``map_call``: reuse a document map that was already requested (avoids a second call).
    """
    text = doc.render()
    if map_call is None:
        map_call = caller.call(DocumentMap, prompts.map_messages(text), name=f"{doc.doc_id}:map")
    result = PipelineResult(doc_id=doc.doc_id, map_call=map_call)
    if not map_call.ok:
        return result
    dmap = map_call.parsed
    assert dmap is not None
    info = document_info(doc, dmap, result.warnings)
    extraction_model = f"{caller.profile.provider}:{caller.profile.model}@{prompts.PROMPT_VERSION}"

    wanted = list(examples) if examples is not None else [e.label for e in dmap.examples]
    known = {e.label: e for e in dmap.examples}
    for label in wanted:
        if label not in known:
            result.warnings.append(f"example {label!r} not in document map")

    taken: set[str] = set()
    quotes = QuoteIndex(doc)

    def resolve(label: str) -> str:
        return make_record_id(doc.doc_id, label)

    for label in wanted:
        ctx = build_example_context(doc, dmap, label)
        call = caller.call(
            ExampleExtraction,
            prompts.example_messages(ctx.render(doc), dmap, label),
            name=f"{doc.doc_id}:{label}",
        )
        outcome = ExampleOutcome(label=label, call=call, context=ctx)
        if ctx.fallback:
            result.warnings.append(
                f"{label}: whole document used as context ({'; '.join(ctx.notes)})"
            )
        if call.ok:
            assert call.parsed is not None
            for rec in call.parsed.records:
                if rec.example_label != label:
                    result.warnings.append(
                        f"asked for {label!r}, record labelled {rec.example_label!r}"
                    )
                rid = unique_id(
                    make_record_id(doc.doc_id, rec.example_label, rec.variant_label), taken
                )
                entry = known.get(rec.example_label) or known.get(label)
                checks = check_record(rec, quotes)
                outcome.ref_checks.extend(checks)
                formulation = to_formulation_record(
                    rec,
                    document=info,
                    record_id=rid,
                    extraction_model=extraction_model,
                    map_is_comparative=entry.is_comparative if entry else None,
                    resolve_example=resolve,
                )
                formulation.warnings.extend(warnings_from(checks))
                outcome.records.append(formulation)
            if ctx.variant_hints and len(call.parsed.records) == 1:
                msg = (f"{len(ctx.variant_hints)} possible experimental variant(s) detected but "
                       f"only one record extracted: {ctx.variant_hints[0]}")  # fmt: skip
                for rec in outcome.records:
                    rec.warnings.append(msg)
        result.examples.append(outcome)
    return result
