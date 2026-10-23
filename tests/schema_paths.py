"""Helpers to flatten Pydantic models into vocab-style paths (``components[].polymer.mw``)."""

from __future__ import annotations

import types
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from negative_lines.schema.refs import SourceRef


def unwrap(annotation: Any) -> tuple[Any, bool]:
    """Strip ``| None`` and one ``list[...]``; return (inner type, is_list)."""
    if get_origin(annotation) in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        annotation = args[0] if len(args) == 1 else Union[tuple(args)]  # noqa: UP007
    if get_origin(annotation) is list:
        return get_args(annotation)[0], True
    return annotation, False


def _is_model(tp: Any) -> bool:
    return isinstance(tp, type) and issubclass(tp, BaseModel) and tp is not SourceRef


def model_paths(model: type[BaseModel], prefix: str = "") -> dict[str, Any]:
    """Leaf path -> (unwrapped) annotation. ``SourceRef`` lists count as one leaf."""
    out: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        inner, is_list = unwrap(field.annotation)
        path = f"{prefix}{name}"
        if _is_model(inner):
            out.update(model_paths(inner, f"{path}[]." if is_list else f"{path}."))
        else:
            out[path] = inner
    return out


def llm_paths() -> dict[str, Any]:
    from negative_lines.schema.llm import DocumentInfo, LLMRecord

    paths = {f"record:{p}": a for p, a in model_paths(LLMRecord).items()}
    paths.update({f"document:{p}": a for p, a in model_paths(DocumentInfo).items()})
    return paths
