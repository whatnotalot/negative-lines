"""LLM-facing schemas must satisfy strict structured-output rules (OpenAI strict, Gemini)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from negative_lines.schema.base import StrictLLMModel
from negative_lines.schema.llm import LLM_SCHEMAS

FORBIDDEN_KEYWORDS = {
    "default",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minItems",
    "maxItems",
    "uniqueItems",
    "patternProperties",
    "oneOf",
    "allOf",
    "not",
    "const",
}
MAX_OBJECT_DEPTH = 6


def _resolve(node: dict, defs: dict) -> dict:
    ref = node.get("$ref")
    return defs[ref.split("/")[-1]] if ref else node


def _walk(node: Any, defs: dict, path: str, depth: int, errors: list[str], seen: tuple) -> int:
    """Validate a schema node; return max object depth below it."""
    if not isinstance(node, dict):
        return depth
    if "$ref" in node:
        name = node["$ref"].split("/")[-1]
        if name in seen:
            errors.append(f"{path}: recursive schema {name}")
            return depth
        return _walk(defs[name], defs, path, depth, errors, (*seen, name))

    bad = FORBIDDEN_KEYWORDS & set(node)
    if bad:
        errors.append(f"{path}: forbidden keywords {sorted(bad)}")
    if isinstance(node.get("type"), list):
        errors.append(f"{path}: type arrays are not allowed")
    if "enum" in node and not all(isinstance(x, str) for x in node["enum"]):
        errors.append(f"{path}: non-string enum {node['enum']}")

    max_depth = depth
    if "anyOf" in node:
        options = [_resolve(o, defs) for o in node["anyOf"]]
        nulls = [o for o in options if o.get("type") == "null"]
        if len(node["anyOf"]) != 2 or len(nulls) != 1:
            errors.append(f"{path}: only 'T | None' unions are allowed")
        for i, opt in enumerate(node["anyOf"]):
            max_depth = max(max_depth, _walk(opt, defs, f"{path}|{i}", depth, errors, seen))

    if node.get("type") == "object":
        props = node.get("properties", {})
        if node.get("additionalProperties") is not False:
            errors.append(f"{path}: additionalProperties must be false")
        if set(node.get("required", [])) != set(props):
            errors.append(f"{path}: all properties must be required")
        if not props:
            errors.append(f"{path}: free-form object")
        for key, sub in props.items():
            max_depth = max(max_depth, _walk(sub, defs, f"{path}.{key}", depth + 1, errors, seen))

    if node.get("type") == "array":
        max_depth = max(max_depth, _walk(node.get("items"), defs, f"{path}[]", depth, errors, seen))
    return max_depth


@pytest.mark.parametrize("schema_cls", LLM_SCHEMAS, ids=lambda c: c.__name__)
def test_json_schema_is_strict(schema_cls):
    schema = schema_cls.model_json_schema()
    defs = schema.get("$defs", {})
    errors: list[str] = []
    depth = _walk(schema, defs, schema_cls.__name__, 1, errors, ())
    assert not errors, "\n".join(errors)
    assert depth <= MAX_OBJECT_DEPTH, f"object nesting depth {depth} > {MAX_OBJECT_DEPTH}"


def _all_models(cls: type[BaseModel], acc: set[type[BaseModel]]) -> set[type[BaseModel]]:
    from schema_paths import unwrap

    if cls in acc:
        return acc
    acc.add(cls)
    for field in cls.model_fields.values():
        inner, _ = unwrap(field.annotation)
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            _all_models(inner, acc)
    return acc


@pytest.mark.parametrize("schema_cls", LLM_SCHEMAS, ids=lambda c: c.__name__)
def test_models_are_strict_and_have_no_defaults(schema_cls):
    for model in _all_models(schema_cls, set()):
        assert issubclass(model, StrictLLMModel), f"{model.__name__} must subclass StrictLLMModel"
        for name, field in model.model_fields.items():
            assert field.is_required(), f"{model.__name__}.{name} must be required (no default)"
            assert (
                field.description
                or model.__name__ in {"ExampleExtraction"}
                or name
                in {
                    "is_comparative",
                    "source_type",
                    "table_id",
                    "content",
                    "document",
                    "tables",
                    "process",
                    "results",
                    "refs",
                    "codename_definitions",
                    "shared_conditions",
                    "grade_scales",
                    "example_label",
                }
            ), f"{model.__name__}.{name} needs a description (it is part of the prompt)"


@pytest.mark.parametrize("schema_cls", LLM_SCHEMAS, ids=lambda c: c.__name__)
def test_gemini_accepts_schema_offline(schema_cls):
    """LangChain's Gemini integration can build a structured-output runnable (no network)."""
    genai = pytest.importorskip("langchain_google_genai")
    llm = genai.ChatGoogleGenerativeAI(model="gemini-3.8-flash", google_api_key="test-not-a-key")
    runnable = llm.with_structured_output(schema_cls, method="json_schema")
    assert runnable is not None
