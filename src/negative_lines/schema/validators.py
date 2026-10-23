"""Labeling-guide rules as small reusable checks.

Each ``check_*`` returns an error message or ``None``. Models call them from
``model_validator``s and raise on hard errors, which lets the extraction
pipeline send the message back to the LLM for one repair attempt.
``collect_warnings`` returns soft issues that are stored with the record but
do not block it.
"""

from __future__ import annotations

import re
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

    w += consistency_warnings(record)
    return w


# ----- consistency checks (warnings only; values are never changed) -------

TOOL_SOURCES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"electron[\s-]*beam|\be-?beam\b|\bEB\b", re.I), "ebeam"),
    (re.compile(r"\bEUV\b|13\.5\s*nm|extreme ultraviolet", re.I), "EUV_13.5"),
    (re.compile(r"\bKrF\b|248\s*nm", re.I), "KrF_248"),
    (re.compile(r"\bArF\b|193\s*nm", re.I), "ArF_193"),
    (re.compile(r"\bi-?line\b|365\s*nm", re.I), "i-line_365"),
    (re.compile(r"\bg-?line\b|436\s*nm", re.I), "g-line_436"),
    (re.compile(r"\bh-?line\b|405\s*nm", re.I), "h-line_405"),
    (re.compile(r"x-?ray", re.I), "other"),
    (re.compile(r"\bion[\s-]*beam\b", re.I), "ion_beam"),
)
_MERCURY_LINES = {"i-line_365", "g-line_436", "h-line_405"}
PAG_HINT = re.compile(
    r"\bPAG\s*-?\d*\b|acid[\s-]*generator|sulfonium|iodonium|oxime\s+sulfonate", re.I
)
AMINE_HINT = re.compile(r"amine\b|\bpyridine\b|\bimidazole\b", re.I)
_LENGTH = re.compile(r"(\d+(?:\.\d+)?)\s*(nm|µm|um|Å)\b")


def expected_source(tool: str | None) -> str | None:
    """Exposure source implied by a tool description, or None if unclear."""
    if not tool:
        return None
    found = {src for pat, src in TOOL_SOURCES if pat.search(tool)}
    if len(found) > 1 and found <= _MERCURY_LINES:
        return "mixed_lines"
    return found.pop() if len(found) == 1 else None


def consistency_warnings(record: Any) -> list[str]:
    w: list[str] = []
    exp = record.process.exposure
    if exp is not None:
        implied = expected_source(exp.tool)
        if implied and exp.source != implied:
            w.append(f"consistency: exposure tool {exp.tool!r} implies source {implied!r}, "
                     f"but source is {exp.source!r}")  # fmt: skip
        if exp.ebeam_kv is not None and exp.source != "ebeam":
            w.append(f"consistency: ebeam_kv given but source is {exp.source!r}")
        if (exp.ion_species or exp.ion_energy_kev is not None) and exp.source != "ion_beam":
            w.append(f"consistency: ion fields given but source is {exp.source!r}")

    resin_100 = any(c.role == "resin" and c.amount_value == 100 for c in record.components)
    for i, c in enumerate(record.components):
        tag = f"components[{i}] ({c.name_as_written})"
        text = " ".join(x for x in (c.name_as_written, c.definition_location, c.note) if x)
        if PAG_HINT.search(text) and c.role not in ("pag", "other"):
            w.append(f"consistency: {tag} looks like a photoacid generator but role is {c.role!r}")
        if AMINE_HINT.search(c.name_as_written) and c.role not in ("quencher", "solvent", "other"):
            w.append(f"consistency: {tag} is an amine (usually 'quencher') but role is {c.role!r}")
        if c.amount_basis == "parts_by_mass" and resin_100:
            w.append(f"consistency: {tag} basis 'parts_by_mass' although the resin is 100 parts: "
                     "probably 'parts_per_100_resin'")  # fmt: skip
        if c.role == "solvent" and re.search(r"[/=]|\band\b", c.name_as_written):
            w.append(
                f"consistency: {tag} looks like a mixed solvent; give one component per solvent"
            )

    coat = record.process.coating
    if coat is not None and coat.film_thickness is not None and coat.underlayer:
        for m in _LENGTH.finditer(coat.underlayer):
            if float(m.group(1)) == coat.film_thickness and (
                coat.film_thickness_unit is None or m.group(2).replace("um", "µm") ==
                (coat.film_thickness_unit or "").replace("um", "µm")
            ):  # fmt: skip
                w.append(f"consistency: resist film_thickness {coat.film_thickness:g} equals the "
                         "underlayer thickness: check that it is the resist film")  # fmt: skip
                break
    sb = record.process.softbake
    if sb is not None:
        for i, s in enumerate(sb.steps):
            if s.time is None and (s.temp_text or "").strip().upper() == "RT":
                w.append(
                    f"consistency: softbake step {i + 1} at RT without time: probably not a bake"
                )
    return w
