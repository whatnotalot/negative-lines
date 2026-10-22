"""Build a LangChain chat model from an ``LLMProfile`` (config/llm.yaml).

Provider and model are configuration: switching between Gemini, OpenAI,
Anthropic or Ollama only needs a new profile (and the matching
``langchain-<provider>`` package), never a code or schema change.
"""

from __future__ import annotations

from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter

from negative_lines.config import LLMProfile, load_env, require_api_key


def build_chat_model(profile: LLMProfile) -> BaseChatModel:
    """Chat model for ``profile``; reads the API key from the environment / ``.env``."""
    load_env()
    require_api_key(profile)
    kwargs: dict[str, Any] = {
        "temperature": profile.temperature,
        "max_retries": profile.max_retries,
    }
    if profile.timeout_s is not None:
        kwargs["timeout"] = profile.timeout_s
    if profile.rpm:
        kwargs["rate_limiter"] = InMemoryRateLimiter(
            requests_per_second=profile.rpm / 60.0, check_every_n_seconds=0.1, max_bucket_size=1
        )
    return init_chat_model(profile.model, model_provider=profile.provider, **kwargs)
