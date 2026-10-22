"""Source references attached to components, results and process groups."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from negative_lines.schema.base import StrictLLMModel

RefPurpose = Literal[
    "value",
    "codename_definition",
    "shared_condition",
    "grade_scale",
    "other",
]


class SourceRef(StrictLLMModel):
    """Pointer to the most specific source location that supports the extracted values."""

    block_id: str = Field(
        description=(
            "ID of the cited block exactly as given in the context, e.g. a paragraph "
            "'p-0045' or a table row 't-2-r-3'. Cite the most specific block (row, not whole table)."
        )
    )
    location: str = Field(
        description="Human-readable location, e.g. '[0045]' or 'Table 2, row Example 3'."
    )
    quote: str = Field(
        description=(
            "Short verbatim excerpt (<= 200 characters) from the cited block containing the "
            "values. Copy exactly; do not paraphrase or translate."
        )
    )
    purpose: RefPurpose = Field(
        description=(
            "Why this block is cited: 'value' for the amounts/conditions/results themselves, "
            "'codename_definition' where a codename such as 'PAG-2' is defined, "
            "'shared_condition' for conditions stated once for several examples, "
            "'grade_scale' for the legend of qualitative grades."
        )
    )
