"""Validated structured-output calls with one repair retry and a disk cache.

Design (see the ``structured-llm-output`` skill):

- The provider constrains decoding with the model's JSON schema (provider-native
  ``json_schema`` method; ``strict`` passed through for OpenAI).
- We pass the schema as a plain dict and validate with Pydantic **ourselves**,
  so the raw JSON is always available, even when our labeling-guide validators
  reject it (some integrations raise instead of returning the error).
- On validation failure the errors and the previous output are sent back for
  ``max_repairs`` attempts. Provider errors (HTTP 4xx/5xx, rejected schema)
  are raised as ``ProviderError`` and never retried here (LangChain already
  retries transient errors via ``max_retries``).
- Responses are cached by provider, model, settings, schema and messages, so
  re-running during development does not spend quota. Cached outputs are
  re-validated, so validator changes take effect immediately.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from negative_lines.config import LLMProfile

T = TypeVar("T", bound=BaseModel)
Message = tuple[str, str]

REPAIR_INSTRUCTIONS = (
    "Your previous JSON output violated these extraction rules:\n{errors}\n\n"
    "Return the complete corrected JSON for the same task. Fix only what these errors require; "
    "keep every other value exactly as copied from the source. If a value cannot be determined "
    "from the source, use null and set confidence 'low' with a note."
)


class ProviderError(RuntimeError):
    """The provider rejected or failed the request (not a validation problem)."""


@dataclass
class CallResult(Generic[T]):
    name: str
    parsed: T | None
    raw: dict[str, Any] | None
    raw_text: str | None
    errors: list[str] = field(default_factory=list)
    attempts: int = 0
    usage: list[dict[str, Any]] = field(default_factory=list)
    cached: bool = False
    error_history: list[list[str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.parsed is not None


def format_validation_errors(exc: ValidationError) -> list[str]:
    """Readable ``path: message`` lines, without echoing input values."""
    out = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        out.append(f"{loc}: {err['msg']}")
    return out


class JsonCache:
    """Tiny content-addressed JSON cache (one file per key)."""

    def __init__(self, directory: Path):
        self.dir = Path(directory)

    def _path(self, key: str) -> Path:
        return self.dir / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        p = self._path(key)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _message_text(msg: Any) -> str | None:
    if msg is None:
        return None
    content = getattr(msg, "content", msg)
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # content blocks (Gemini/Anthropic)
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


def _usage(msg: Any) -> dict[str, Any]:
    usage = getattr(msg, "usage_metadata", None)
    return dict(usage) if usage else {}


class StructuredCaller:
    """Call an LLM for one Pydantic schema, validate, repair, cache."""

    def __init__(
        self,
        llm: Any,
        profile: LLMProfile,
        *,
        cache: JsonCache | None = None,
        max_repairs: int = 1,
        prompt_version: str = "",
    ):
        self.llm = llm
        self.profile = profile
        self.cache = cache
        self.max_repairs = max_repairs
        self.prompt_version = prompt_version
        self._runnables: dict[type[BaseModel], Any] = {}

    # ----- internals ---------------------------------------------------

    def _runnable(self, schema: type[BaseModel]) -> Any:
        if schema not in self._runnables:
            kwargs: dict[str, Any] = {}
            if self.profile.strict is not None:
                kwargs["strict"] = self.profile.strict
            self._runnables[schema] = self.llm.with_structured_output(
                schema.model_json_schema(),
                method=self.profile.structured_method,
                include_raw=True,
                **kwargs,
            )
        return self._runnables[schema]

    def cache_key(self, schema: type[BaseModel], messages: list[Message]) -> str:
        payload = {
            "provider": self.profile.provider,
            "model": self.profile.model,
            "temperature": self.profile.temperature,
            "method": self.profile.structured_method,
            "strict": self.profile.strict,
            "prompt_version": self.prompt_version,
            "schema": schema.model_json_schema(),
            "messages": messages,
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def _invoke(self, schema: type[BaseModel], messages: list[Message]) -> dict[str, Any]:
        key = self.cache_key(schema, messages)
        if self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                return hit | {"cached": True}
        try:
            out = self._runnable(schema).invoke(messages)
        except Exception as exc:  # provider-side failure
            raise ProviderError(f"{type(exc).__name__}: {exc}") from exc
        raw_msg = out.get("raw")
        parsed = out.get("parsed")
        entry = {
            "raw": parsed if isinstance(parsed, dict) else None,
            "raw_text": _message_text(raw_msg),
            "parsing_error": str(out["parsing_error"]) if out.get("parsing_error") else None,
            "usage": _usage(raw_msg),
        }
        if self.cache is not None and entry["raw"] is not None:
            self.cache.set(key, entry)
        return entry | {"cached": False}

    # ----- public ------------------------------------------------------

    def call(self, schema: type[T], messages: list[Message], *, name: str) -> CallResult[T]:
        msgs = list(messages)
        result: CallResult[T] = CallResult(name=name, parsed=None, raw=None, raw_text=None)
        for attempt in range(1, self.max_repairs + 2):
            entry = self._invoke(schema, msgs)
            result.attempts = attempt
            result.raw, result.raw_text = entry["raw"], entry["raw_text"]
            result.cached = entry["cached"]
            if entry["usage"]:
                result.usage.append(entry["usage"])
            if entry["raw"] is None:
                errors = [f"<root>: output is not valid JSON ({entry.get('parsing_error')})"]
            else:
                try:
                    result.parsed = schema.model_validate(entry["raw"])
                    result.errors = []
                    return result
                except ValidationError as exc:
                    errors = format_validation_errors(exc)
            result.errors = errors
            result.error_history.append(errors)
            if attempt <= self.max_repairs:
                msgs = [
                    *msgs,
                    ("ai", entry["raw_text"] or json.dumps(entry["raw"], ensure_ascii=False)),
                    (
                        "human",
                        REPAIR_INSTRUCTIONS.format(errors="\n".join(f"- {e}" for e in errors)),
                    ),
                ]
        return result
