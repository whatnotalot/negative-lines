"""LLM profiles are configuration; API keys come only from the environment."""

from __future__ import annotations

import pytest

from negative_lines.config import (
    MissingAPIKeyError,
    Settings,
    load_llm_profile,
    require_api_key,
)


def test_default_profile_is_gemini_flash():
    profile = load_llm_profile(settings=Settings(llm_profile=None))
    assert profile.provider == "google_genai"
    assert profile.structured_method == "json_schema"
    assert profile.api_key_env == "GOOGLE_API_KEY"


def test_profile_selectable_by_setting():
    assert (
        load_llm_profile(settings=Settings(llm_profile="gemini_flash_lite")).name
        == "gemini_flash_lite"
    )


def test_unknown_profile_fails():
    with pytest.raises(KeyError):
        load_llm_profile("nope", settings=Settings())


def test_missing_key_raises_without_leaking(monkeypatch):
    profile = load_llm_profile(settings=Settings(llm_profile=None))
    monkeypatch.delenv(profile.api_key_env, raising=False)
    with pytest.raises(MissingAPIKeyError, match=profile.api_key_env):
        require_api_key(profile)
    monkeypatch.setenv(profile.api_key_env, "secret-value-123")
    require_api_key(profile)
    assert "secret-value-123" not in repr(profile)


def test_llm_config_contains_no_secrets():
    text = Settings().llm_config_path.read_text(encoding="utf-8")
    assert "AIza" not in text and "sk-" not in text
