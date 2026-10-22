"""Labeling-guide rules as small reusable checks.

Each ``check_*`` returns an error message or ``None``. Models call them from
``model_validator``s and raise on hard errors, which lets the extraction
pipeline send the message back to the LLM for one repair attempt.
``collect_warnings`` returns soft issues that are stored with the record but
do not block it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from negative_lines.vocab import get_vocab


def raise_if(errors: Iterable[str | None]) -> None:
    msgs = [e for e in errors if e]
    if msgs:
        raise ValueError("; ".join(msgs))


# ----- hard checks ------------------------------------------------------


def check_other_text(field: str, value: str | None, other_text: str | None) -> str | None:
    if value == "other" and not (other_text and other_text.strip()):
        return f"{field} is 'other' but the free-text description is empty"
    return None


def check_value_xor_text(field: str, value: Any, text: str | None) -> str | None:
    if value is not None and text is not None:
        return f"{field}: set either the numeric value or the text form, not both"
    return None


def check_amount_has_basis(has_amount: bool, basis: str | None) -> str | None:
    if has_amount and basis is None:
        return (
            "amount given without amount_basis (use 'unspecified' with low confidence if unclear)"
        )
    return None


def check_low_confidence(condition: bool, what: str, confidence: str | None) -> str | None:
    if condition and confidence != "low":
        return f"{what} requires confidence 'low'"
    return None


def check_sigma(sigma: int | None) -> str | None:
    if sigma is not None and sigma not in (1, 3):
        return f"sigma must be 1 or 3, got {sigma}"
    return None


def check_result_has_evidence(
    value: float | None, value_qualitative: str | None, figure_only: bool
) -> str | None:
    if value is None and value_qualitative is None and not figure_only:
        return "result has neither value nor value_qualitative; set figure_only if only a figure shows it"
    return None


def check_not_digitized(value: float | None, figure_only: bool) -> str | None:
    """Figure-only results must not carry a number read off a plot."""
    if figure_only and value is not None:
        return "figure_only result must have value null (never read values off plots); if the number is stated in text or a caption, set figure_only false"
    return None


def check_nonblank(field: str, text: str | None) -> str | None:
    if text is None or not text.strip():
        return f"{field} must be copied from the source (empty)"
    return None


def check_dose_has_unit(dose: float | None, dose_unit: str | None) -> str | None:
    """A dose is meaningless without its printed unit (checklist: dose unit as printed)."""
    if dose is not None and dose_unit is None:
        return "dose given without dose_unit; copy the unit as printed ('other' + note if unusual)"
    return None


def check_dose_unit(source: str | None, dose_unit: str | None) -> str | None:
    """Dose unit must belong to the exposure source's dose family (never convert families)."""
    if source is None or dose_unit is None:
        return None
    allowed = get_vocab().dose_units_for_source(source)
    if "as_written" in allowed:
        return None
    if dose_unit not in allowed:
        return f"dose_unit {dose_unit!r} is not valid for source {source!r} (allowed: {sorted(allowed)})"
    return None


def check_refs_present(field: str, refs: Sequence[Any], has_content: bool = True) -> str | None:
    if has_content and not refs:
        return f"{field} has values but no source reference"
    return None


def check_fraction(
    field: str, value: float | None, lo: float = 0.0, hi: float = 100.0
) -> str | None:
    if value is not None and not (lo <= value <= hi):
        return f"{field}={value} outside [{lo}, {hi}]"
    return None


# ----- soft checks ------------------------------------------------------


def _zero_paths(obj: Any, prefix: str = "") -> list[str]:
    """Paths of numeric fields that are exactly 0 (missing must be null, not 0)."""
    from pydantic import BaseModel

    out: list[str] = []
    if isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            out += _zero_paths(getattr(obj, name), f"{prefix}{name}.")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            out += _zero_paths(item, f"{prefix[:-1]}[{i}].")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool) and obj == 0:
        out.append(prefix[:-1])
    return out


def _times(process: Any) -> list[tuple[str, float | None, str | None]]:
    """(path, time, time_unit) for every time field of an ``LLMProcess``."""
    out: list[tuple[str, float | None, str | None]] = []
    if process.softbake is not None:
        for i, s in enumerate(process.softbake.steps):
            out.append((f"process.softbake.steps[{i}]", s.time, s.time_unit))
    for name in ("peb", "development", "hardbake"):
        group = getattr(process, name)
        if group is not None:
            out.append((f"process.{name}", group.time, group.time_unit))
    if process.exposure is not None:
        e = process.exposure
        out.append(("process.exposure.exposure_time", e.exposure_time, e.exposure_time_unit))
    return out


def collect_warnings(record: Any) -> list[str]:
    """Soft issues for an ``LLMRecord`` (duck-typed to avoid an import cycle)."""
    w: list[str] = []

    for path in _zero_paths(record):
        if not path.endswith("refs"):
            w.append(f"{path} is 0: confirm it was measured as zero (missing must be null)")

    if not record.refs:
        w.append("record has no record-level source reference")

    for basis in ("wt_pct_solids", "wt_pct_total"):
        amounts = [
            c.amount_value
            for c in record.components
            if c.amount_basis == basis
            and c.amount_value is not None
            and (basis == "wt_pct_total" or c.role != "solvent")
        ]
        if amounts and sum(amounts) > 100.5:
            w.append(
                f"{basis} amounts sum to {sum(amounts):.1f} > 100: probably parts, not percent"
            )

    for i, c in enumerate(record.components):
        if (c.amount_value is not None or c.amount_text is not None) and c.amount_unit is None:
            w.append(f"components[{i}] ({c.name_as_written}): amount without amount_unit")

    for path, time, unit in _times(record.process):
        if time is not None and unit is None:
            w.append(f"{path}: time without time unit")

    exp = record.process.exposure
    if exp is not None:
        if exp.source == "ebeam" and exp.ebeam_kv is None:
            w.append("ebeam exposure without ebeam_kv")
        if (
            exp.dose is not None
            and exp.intensity_mw_cm2 is not None
            and exp.exposure_time is not None
        ):
            w.append("dose and intensity x time both given: keep dose only if the source states it")
        if record.coating_only:
            w.append("coating_only is true but exposure conditions are present")

    for i, r in enumerate(record.results):
        tag = f"results[{i}] ({r.metric})"
        if r.metric == "dose_sat" and r.threshold_pct is None:
            w.append(f"{tag}: dose_sat without threshold_pct")
        if r.metric in ("ler_3sigma_nm", "lwr_3sigma_nm") and r.sigma is None:
            w.append(f"{tag}: roughness without sigma")
        if r.metric == "resolution_min_cd_nm" and r.pitch_value is None and r.pattern_type is None:
            w.append(f"{tag}: resolution without pitch or pattern_type")
        if r.metric == "sensitivity_esize" and r.condition is None:
            w.append(f"{tag}: Esize without target CD/pitch in condition")

    return w
