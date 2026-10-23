"""Runtime settings and LLM profile loading.

Secrets are never stored here. Provider API keys are read from environment
variables (optionally populated from a local, gitignored ``.env`` file); a
profile only names *which* variable holds its key.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Non-secret settings, overridable with ``NL_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="NL_", env_file=REPO_ROOT / ".env", extra="ignore")

    llm_profile: str | None = None
    llm_config_path: Path = REPO_ROOT / "config" / "llm.yaml"
    vocab_path: Path = REPO_ROOT / "vocab.yaml"
    cache_dir: Path = REPO_ROOT / "data" / "cache"
    raw_dir: Path = REPO_ROOT / "data" / "raw"
    extracted_dir: Path = REPO_ROOT / "data" / "extracted"  # committed extraction runs
    # gold set (see eval/split.yaml): development is committed, benchmark stays external
    gold_dev_path: Path = REPO_ROOT / "data" / "gold" / "v0" / "development.xlsx"
    gold_benchmark_path: Path | None = None  # NL_GOLD_BENCHMARK_PATH, milestone runs only


class LLMProfile(BaseModel):
    """One provider/model configuration from ``config/llm.yaml``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    provider: str
    model: str
    api_key_env: str | None = None
    temperature: float = 0.0
    structured_method: Literal["json_schema", "function_calling", "json_mode"] = "json_schema"
    strict: bool | None = None
    rpm: float | None = None
    max_retries: int = 3
    timeout_s: float | None = 120


class MissingAPIKeyError(RuntimeError):
    pass


def load_env() -> None:
    """Load ``.env`` into the process environment without overriding real env vars."""
    load_dotenv(REPO_ROOT / ".env", override=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def load_llm_profile(name: str | None = None, settings: Settings | None = None) -> LLMProfile:
    """Return the requested profile, else ``NL_LLM_PROFILE``, else the file's default."""
    settings = settings or get_settings()
    data = yaml.safe_load(settings.llm_config_path.read_text(encoding="utf-8"))
    profiles = data.get("profiles") or {}
    chosen = name or settings.llm_profile or data.get("default_profile")
    if chosen not in profiles:
        raise KeyError(f"LLM profile {chosen!r} not found; available: {sorted(profiles)}")
    return LLMProfile(name=chosen, **profiles[chosen])


def require_api_key(profile: LLMProfile) -> None:
    """Fail early (without ever printing the key) if the profile's key env var is unset."""
    if profile.api_key_env and not os.environ.get(profile.api_key_env):
        raise MissingAPIKeyError(
            f"Environment variable {profile.api_key_env} is not set for LLM profile "
            f"{profile.name!r}. Put it in your shell environment or in a local .env file."
        )
