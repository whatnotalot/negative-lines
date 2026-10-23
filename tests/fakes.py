"""Offline stand-in for a LangChain chat model with structured output.

Mimics what ``with_structured_output(schema_dict, include_raw=True)`` returns
for real providers: ``{"raw": AIMessage, "parsed": dict | None,
"parsing_error": ... }``. Responses are scripted per schema title, so tests
are deterministic and never touch the network.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

Response = dict[str, Any] | str  # dict = JSON object; str = raw (possibly invalid) text


class FakeStructuredLLM:
    def __init__(self, scripted: dict[str, list[Response]]):
        """``scripted`` maps a schema title (e.g. 'ExampleExtraction') to responses in order."""
        self.scripted = {k: list(v) for k, v in scripted.items()}
        self.calls: dict[str, list[list[tuple[str, str]]]] = defaultdict(list)
        self.bind_kwargs: dict[str, dict[str, Any]] = {}

    def with_structured_output(self, schema: dict[str, Any], **kwargs: Any) -> RunnableLambda:
        title = schema["title"]
        self.bind_kwargs[title] = kwargs

        def respond(messages: list[tuple[str, str]]) -> dict[str, Any]:
            self.calls[title].append(list(messages))
            queue = self.scripted.get(title) or []
            if not queue:
                raise AssertionError(f"no scripted response left for {title}")
            resp = queue.pop(0)
            if isinstance(resp, str):
                try:
                    parsed, err = json.loads(resp), None
                except json.JSONDecodeError as exc:
                    parsed, err = None, exc
                text = resp
            else:
                parsed, err, text = resp, None, json.dumps(resp)
            msg = AIMessage(
                content=text,
                usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            )
            return {"raw": msg, "parsed": parsed, "parsing_error": err}

        return RunnableLambda(respond)

    def n_calls(self, title: str) -> int:
        return len(self.calls[title])


class ExplodingLLM:
    """Simulates a provider rejecting the request (e.g. HTTP 400 schema too complex)."""

    def with_structured_output(self, schema: dict[str, Any], **kwargs: Any) -> RunnableLambda:
        def boom(_messages):
            raise RuntimeError("400 INVALID_ARGUMENT: schema too complex")

        return RunnableLambda(boom)
