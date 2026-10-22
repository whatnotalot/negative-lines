"""Level-2 integration (OPT-IN, PAID): the configured provider accepts our schemas.

Never runs in the normal suite: ``pyproject.toml`` deselects the ``live`` marker.
Run explicitly with::

    uv run pytest -m live -rP

Uses the active profile (``NL_LLM_PROFILE`` / config/llm.yaml) and the API key
from the environment or ``.env``; skips if the key is missing. Input is the
SYNTHETIC ingestion fixture (no real or gold-set documents). Two calls,
~10k tokens. No cache and no repair retry, so the provider is really exercised.

Hard assertions are only about the provider contract: the request is accepted
(no ProviderError) and the output is well-formed JSON for the schema. Whether
the output also passes the labeling-guide validators is extraction QUALITY:
it is reported (printed and written to data/interim/live/), not asserted, so
trying a weaker model does not turn the suite red.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from builders import document_map

from negative_lines.config import REPO_ROOT, load_env, load_llm_profile
from negative_lines.extract import prompts
from negative_lines.ingest.document import SourceDocument
from negative_lines.llm import CallResult, StructuredCaller, build_chat_model
from negative_lines.schema.llm import DocumentMap, ExampleExtraction

pytestmark = pytest.mark.live

FIXTURE = Path(__file__).parent / "fixtures" / "ingest" / "expected_blocks.json"
REPORT_DIR = REPO_ROOT / "data" / "interim" / "live"


@pytest.fixture(scope="module")
def caller() -> StructuredCaller:
    load_env()
    profile = load_llm_profile()
    if profile.api_key_env and not os.environ.get(profile.api_key_env):
        pytest.skip(f"{profile.api_key_env} not set for profile {profile.name!r}")
    return StructuredCaller(
        build_chat_model(profile), profile, cache=None, max_repairs=0,
        prompt_version=prompts.PROMPT_VERSION,
    )  # fmt: skip


@pytest.fixture(scope="module")
def doc() -> SourceDocument:
    return SourceDocument.model_validate(
        json.loads(FIXTURE.read_text(encoding="utf-8"))["document"]
    )


def report(call: CallResult, caller: StructuredCaller) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    p = caller.profile
    entry = {
        "profile": p.name,
        "model": f"{p.provider}:{p.model}",
        "prompt_version": prompts.PROMPT_VERSION,
        "call": call.name,
        "valid": call.ok,
        "validation_errors": call.errors,
        "usage": call.usage,
        "raw": call.raw,
    }
    path = REPORT_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}_{call.name.replace(':', '_')}.json"
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    status = "VALID" if call.ok else f"INVALID ({len(call.errors)} guide-rule errors)"
    print(f"\n[{call.name}] {p.provider}:{p.model} -> {status}; usage={call.usage}")
    for e in call.errors:
        print("   -", e)
    print("   report:", path)


def test_provider_accepts_document_map_schema(caller, doc):
    call = caller.call(DocumentMap, prompts.map_messages(doc.render()), name="live:map")
    report(call, caller)
    assert call.raw is not None, "provider returned no well-formed JSON object"


def test_provider_accepts_example_extraction_schema(caller, doc):
    # fixed map, so this test does not depend on the map call's quality
    dmap = DocumentMap.model_validate(
        document_map(
            [("Example 1", False), ("Example 2", False), ("Comparative Example 1", True)],
            doc_id=doc.doc_id,
        )
    )
    call = caller.call(
        ExampleExtraction,
        prompts.example_messages(doc.render(), dmap, "Example 1"),
        name="live:Example 1",
    )
    report(call, caller)
    assert call.raw is not None, "provider returned no well-formed JSON object"
