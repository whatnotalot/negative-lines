"""Base class for every model that is sent to an LLM as a structured-output schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictLLMModel(BaseModel):
    """Strict-JSON-schema-compatible base.

    Rules for subclasses (enforced by ``tests/test_schema_strict.py``):

    - every field is required (no defaults); "not stated" is ``T | None`` set to null
    - unions only of the form ``T | None``; enums only as string ``Literal``
    - no dicts, ``Any`` or tuples; no numeric/string constraints in the schema
      (validate in Python instead)
    """

    model_config = ConfigDict(extra="forbid")
