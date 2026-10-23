"""Command line: ``negative-lines <command>``.

    negative-lines ingest   <doc_id>                 # fetch + parse only, no LLM
    negative-lines examples <doc_id>                 # ingest + 1 document-map call
    negative-lines extract  <doc_id> [-e LABEL ...]  # full extraction, writes data/extracted/

Run ``negative-lines <command> --help`` for options. Exit codes: 0 ok, 1 some
examples failed validation, 2 refused (benchmark document, missing API key,
too many examples).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence

from negative_lines.config import MissingAPIKeyError, get_settings


def _ingest(doc_id: str):
    from negative_lines.ingest.google_patents import ingest_google_patent

    return ingest_google_patent(doc_id)


def cmd_ingest(args: argparse.Namespace) -> int:
    doc = _ingest(args.doc_id)
    kinds = Counter(b.kind for b in doc.blocks)
    print(f"{doc.doc_id} | {doc.title} | {doc.assignee_or_authors} | {doc.year} | {doc.language}")
    print("source:", doc.url)
    print("blocks:", len(doc.blocks), dict(kinds))
    tables = Counter(b.table_id for b in doc.blocks if b.kind == "table_row")
    print("tables:", dict(tables) or "none")
    print("headings:", "; ".join(b.text for b in doc.blocks if b.kind == "heading"))
    print("prompt context:", len(doc.render()), "characters")
    if args.blocks:
        for b in doc.blocks[: args.blocks]:
            print(f"  [{b.block_id}] {b.text[:160]}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            fh.write(doc.model_dump_json(indent=2))
        print("written:", args.json)
    return 0


def cmd_examples(args: argparse.Namespace) -> int:
    from negative_lines.extract.api import list_examples

    labels = list_examples(
        _ingest(args.doc_id),
        profile=args.profile,
        use_cache=not args.no_cache,
        allow_benchmark=args.allow_benchmark,
    )
    print(f"{len(labels)} examples:")
    for label, comparative in labels:
        print(f"  {label}{'  (comparative)' if comparative else ''}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    from negative_lines.extract.api import extract_patent

    run = extract_patent(
        _ingest(args.doc_id),
        examples=args.example or None,
        profile=args.profile,
        max_examples=args.max_examples,
        use_cache=not args.no_cache,
        allow_benchmark=args.allow_benchmark,
        out_dir=None if args.no_write else (args.out_dir or get_settings().extracted_dir),
        max_repairs=args.max_repairs,
    )
    s = run.summary()
    print(f"{s['doc_id']} with {s['model']} (prompt {s['prompt_version']})")
    print(f"examples: {len(s['examples_requested'])} requested, "
          f"{len(s['examples_requested']) - len(s['failed_examples'])} ok, "
          f"{len(s['failed_examples'])} failed; records: {s['records']}")  # fmt: skip
    for ex in run.result.examples:
        state = "ok" if ex.call.ok else "FAILED"
        cached = " (cached)" if ex.call.cached else ""
        print(
            f"  {ex.label}: {state}, {len(ex.records)} record(s), {ex.call.attempts} attempt(s){cached}"
        )
        for e in ex.call.errors[:5]:
            print(f"      - {e}")
        if ex.ref_checks:
            rs = ex.ref_summary()
            print(f"      refs: {rs['verified']}/{rs['total']} quotes found in the cited block "
                  f"({rs['elsewhere']} elsewhere, {rs['not_found']} not found, "
                  f"{rs['unknown_block']} unknown block)")  # fmt: skip
        for r in ex.records:
            if r.warnings:
                print(f"      {r.record_id}: {len(r.warnings)} warning(s), e.g. {r.warnings[0]}")
    u = s["usage"]
    print(f"usage: {u['input_tokens']} input + {u['output_tokens']} output tokens billed, "
          f"{u['cached_calls']}/{u['calls']} calls from cache")  # fmt: skip
    for w in s["warnings"] + s["notes"]:
        print("note:", w)
    if run.paths:
        print("written:", run.paths["run"].parent)
    if args.print_records:
        for r in run.records:
            print(json.dumps(r.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if not s["failed_examples"] and s["map_ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="negative-lines", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("ingest", help="fetch and parse a Google Patents page (no LLM)")
    pi.add_argument("doc_id")
    pi.add_argument("--blocks", type=int, default=0, help="print the first N blocks")
    pi.add_argument("--json", help="write the parsed SourceDocument to this file")
    pi.set_defaults(func=cmd_ingest)

    def llm_opts(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--profile", help="LLM profile from config/llm.yaml (default: NL_LLM_PROFILE)"
        )
        sp.add_argument("--no-cache", action="store_true", help="ignore data/cache/")
        sp.add_argument("--allow-benchmark", action="store_true",
                        help="permit reserved benchmark documents (approved milestone runs only)")  # fmt: skip

    pe = sub.add_parser("examples", help="list the examples found by the document map (1 LLM call)")
    pe.add_argument("doc_id")
    llm_opts(pe)
    pe.set_defaults(func=cmd_examples)

    px = sub.add_parser("extract", help="extract records and write them to data/extracted/")
    px.add_argument("doc_id")
    px.add_argument("-e", "--example", action="append",
                    help="example label as listed by `examples` (repeatable); default: all")  # fmt: skip
    px.add_argument("--max-examples", type=int, default=None,
                    help="refuse to run if more examples would be extracted")  # fmt: skip
    px.add_argument("--max-repairs", type=int, default=1)
    px.add_argument("--out-dir", help="default: data/extracted/")
    px.add_argument("--no-write", action="store_true", help="do not write output files")
    px.add_argument("--print-records", action="store_true")
    llm_opts(px)
    px.set_defaults(func=cmd_extract)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    from negative_lines.extract.api import TooManyExamplesError
    from negative_lines.gold.split import BenchmarkAccessError

    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (BenchmarkAccessError, MissingAPIKeyError, TooManyExamplesError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
