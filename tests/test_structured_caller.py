"""Step 4: StructuredCaller (validate ourselves, repair once, cache) and the factory."""

from __future__ import annotations

import pytest
from builders import document_map, record, result
from fakes import ExplodingLLM, FakeStructuredLLM

from negative_lines.config import LLMProfile, Settings, load_llm_profile
from negative_lines.llm import JsonCache, ProviderError, StructuredCaller, build_chat_model
from negative_lines.schema.llm import DocumentMap, ExampleExtraction

PROFILE = LLMProfile(
    name="fake", provider="fake", model="fake-1", api_key_env=None, strict=True,
    structured_method="json_schema",
)  # fmt: skip
MSGS = [("system", "rules"), ("human", "extract Example 1")]


def extraction(*records: dict) -> dict:
    return {"example_label": "Example 1", "records": list(records), "note": None}


BAD = extraction(record(results=[result(metric="sensitivity_unspecified", confidence="high")]))
GOOD = extraction(record(results=[result(metric="sensitivity_unspecified", confidence="low")]))


def test_valid_output_first_try():
    llm = FakeStructuredLLM({"ExampleExtraction": [GOOD]})
    res = StructuredCaller(llm, PROFILE).call(ExampleExtraction, MSGS, name="t")
    assert res.ok and res.attempts == 1 and res.errors == []
    assert isinstance(res.parsed, ExampleExtraction)
    assert res.usage == [{"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}]
    # provider-native structured output with our JSON schema, strict passed through
    assert llm.bind_kwargs["ExampleExtraction"] == {
        "method": "json_schema",
        "include_raw": True,
        "strict": True,
    }


def test_repair_retry_sends_errors_and_previous_output():
    llm = FakeStructuredLLM({"ExampleExtraction": [BAD, GOOD]})
    res = StructuredCaller(llm, PROFILE, max_repairs=1).call(ExampleExtraction, MSGS, name="t")
    assert res.ok and res.attempts == 2
    assert res.error_history == [
        [
            "records.0.results.0: Value error, metric 'sensitivity_unspecified' requires "
            "confidence 'low'"
        ]
    ]
    second = llm.calls["ExampleExtraction"][1]
    assert second[:2] == MSGS
    assert second[2][0] == "ai" and '"sensitivity_unspecified"' in second[2][1]
    assert second[3][0] == "human" and "requires confidence 'low'" in second[3][1]


def test_gives_up_after_max_repairs_and_keeps_raw():
    llm = FakeStructuredLLM({"ExampleExtraction": [BAD, BAD]})
    res = StructuredCaller(llm, PROFILE, max_repairs=1).call(ExampleExtraction, MSGS, name="t")
    assert not res.ok and res.attempts == 2
    assert res.raw is not None and res.raw_text is not None
    assert "requires confidence 'low'" in res.errors[0]


def test_invalid_json_is_a_validation_failure_not_a_crash():
    llm = FakeStructuredLLM({"DocumentMap": ["{not json", document_map([("Example 1", False)])]})
    res = StructuredCaller(llm, PROFILE).call(DocumentMap, MSGS, name="t")
    assert res.ok and res.attempts == 2
    assert "not valid JSON" in res.error_history[0][0]


def test_provider_errors_raise_and_are_not_repaired():
    with pytest.raises(ProviderError, match="schema too complex"):
        StructuredCaller(ExplodingLLM(), PROFILE).call(DocumentMap, MSGS, name="t")


def test_cache_hit_skips_provider_and_revalidates(tmp_path):
    cache = JsonCache(tmp_path)
    llm = FakeStructuredLLM({"ExampleExtraction": [GOOD]})
    first = StructuredCaller(llm, PROFILE, cache=cache).call(ExampleExtraction, MSGS, name="t")
    assert first.ok and not first.cached
    again = StructuredCaller(FakeStructuredLLM({}), PROFILE, cache=cache).call(
        ExampleExtraction, MSGS, name="t"
    )
    assert again.ok and again.cached


def test_cache_key_depends_on_model_prompt_version_and_messages():
    a = StructuredCaller(None, PROFILE, prompt_version="v1")
    b = StructuredCaller(None, PROFILE.model_copy(update={"model": "fake-2"}), prompt_version="v1")
    c = StructuredCaller(None, PROFILE, prompt_version="v2")
    keys = {
        a.cache_key(ExampleExtraction, MSGS),
        b.cache_key(ExampleExtraction, MSGS),
        c.cache_key(ExampleExtraction, MSGS),
        a.cache_key(ExampleExtraction, [*MSGS, ("human", "more")]),
        a.cache_key(DocumentMap, MSGS),
    }
    assert len(keys) == 5


def test_factory_builds_profile_model_offline(monkeypatch):
    """No network: building the client only needs a (dummy) key in the environment."""
    profile = load_llm_profile("openai_mini", settings=Settings())
    monkeypatch.setenv(profile.api_key_env, "dummy-offline")
    llm = build_chat_model(profile)
    assert type(llm).__name__ == "ChatOpenAI"
    assert llm.model_name == "gpt-4o-mini"
    assert llm.temperature == 0.0
