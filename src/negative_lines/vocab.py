"""Loader for ``vocab.yaml``, the single source of truth for the controlled vocabulary.

The Pydantic models use static ``Literal`` types (see ``schema/enums.py``) for
readability; this module exposes the YAML at runtime for validators, unit
tables and the consistency tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any

import yaml

#: vocab.yaml sections that are plain lists of allowed values
LIST_ENUMS = (
    "source_types",
    "labeler_confidence",
    "exposure_modes",
    "dose_types",
    "thickness_stages",
    "bake_methods",
    "developer_methods",
    "pattern_types",
    "compliance_rules",
)

#: vocab.yaml sections that are mappings whose keys are the allowed values
MAPPING_ENUMS = (
    "roles",
    "amount_bases",
    "exposure_sources",
    "metrics",
    "reconciliation_causes",
)


@dataclass(frozen=True)
class Vocab:
    raw: dict[str, Any]
    path: Path

    @property
    def version(self) -> int:
        return int(self.raw["version"])

    def enum(self, name: str) -> frozenset[str]:
        """Allowed values of an enumeration section."""
        section = self.raw[name]
        if name in LIST_ENUMS:
            return frozenset(str(v) for v in section)
        if name in MAPPING_ENUMS:
            return frozenset(str(k) for k in section)
        raise KeyError(f"{name!r} is not an enumeration section of vocab.yaml")

    # ----- units ---------------------------------------------------------

    @cached_property
    def length_units(self) -> dict[str, float]:
        """Accepted length units -> factor to nm."""
        return {str(k): float(v) for k, v in self.raw["units"]["length"]["accepted"].items()}

    @cached_property
    def time_units(self) -> dict[str, float]:
        """Accepted time units -> factor to seconds."""
        return {str(k): float(v) for k, v in self.raw["units"]["time"]["accepted"].items()}

    @cached_property
    def dose_families(self) -> dict[str, frozenset[str]]:
        fams = self.raw["units"]["dose"]["families"]
        return {str(k): frozenset(str(u) for u in v) for k, v in fams.items()}

    @cached_property
    def dose_units(self) -> frozenset[str]:
        return frozenset().union(*self.dose_families.values())

    def dose_family_of(self, unit: str) -> str | None:
        for family, units in self.dose_families.items():
            if unit in units:
                return family
        return None

    def dose_units_for_source(self, source: str) -> frozenset[str]:
        """Dose units allowed for an exposure source (``as_written`` = anything)."""
        return frozenset(str(u) for u in self.raw["exposure_sources"][source]["dose_units"])

    # ----- record schema -------------------------------------------------

    @cached_property
    def record_fields(self) -> dict[str, dict[str, Any]]:
        """Flattened record schema: ``"components[].polymer.mw" -> field spec``."""
        out: dict[str, dict[str, Any]] = {}
        _walk_record(self.raw["record"], "", out)
        return out

    @cached_property
    def computed_fields(self) -> frozenset[str]:
        return frozenset(p for p, spec in self.record_fields.items() if spec.get("computed"))


def _walk_record(node: dict[str, Any], prefix: str, out: dict[str, dict[str, Any]]) -> None:
    for key, spec in node.items():
        path = f"{prefix}{key}"
        if not isinstance(spec, dict):
            continue
        if "type" in spec:
            if spec["type"] == "list" and isinstance(spec.get("item"), dict):
                _walk_record(spec["item"], f"{path}[].", out)
            else:
                out[path] = spec
        else:  # a group of fields, e.g. provenance, process.exposure
            _walk_record(spec, f"{path}.", out)


def load_vocab(path: Path | str) -> Vocab:
    path = Path(path)
    return Vocab(raw=yaml.safe_load(path.read_text(encoding="utf-8")), path=path)


@lru_cache(maxsize=1)
def get_vocab() -> Vocab:
    """The project vocab (path from settings, ``NL_VOCAB_PATH`` to override)."""
    from negative_lines.config import get_settings

    return load_vocab(get_settings().vocab_path)
