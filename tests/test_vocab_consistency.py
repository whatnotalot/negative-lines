"""The static schema must agree with vocab.yaml (the source of truth)."""

from __future__ import annotations

from typing import Literal, get_args, get_origin

import pytest
from schema_paths import llm_paths, model_paths

from negative_lines.schema import enums, mapping
from negative_lines.schema.record import FormulationRecord
from negative_lines.vocab import get_vocab

VOCAB = get_vocab()
VOCAB_PATHS = VOCAB.record_fields
RECORD_PATHS = model_paths(FormulationRecord)
LLM_PATHS = llm_paths()


def literal_values(tp) -> frozenset[str]:
    assert get_origin(tp) is Literal, f"{tp} is not a Literal"
    return frozenset(get_args(tp))


def vocab_enum_values(values_ref: str) -> frozenset[str]:
    if values_ref == "units.length":
        return frozenset(VOCAB.length_units)
    if values_ref == "units.time":
        return frozenset(VOCAB.time_units)
    return VOCAB.enum(values_ref)


# ----- enumerations -----------------------------------------------------


def test_vocab_version_matches():
    assert enums.VOCAB_VERSION == VOCAB.version, "bump VOCAB_VERSION in schema/enums.py"


@pytest.mark.parametrize("section", sorted(enums.VOCAB_ENUM_MIRRORS))
def test_enum_mirrors_vocab(section):
    lit = enums.VOCAB_ENUM_MIRRORS[section]
    assert literal_values(lit) == VOCAB.enum(section)


def test_every_vocab_enum_section_is_mirrored():
    from negative_lines.vocab import LIST_ENUMS, MAPPING_ENUMS

    assert set(LIST_ENUMS) | set(MAPPING_ENUMS) == set(enums.VOCAB_ENUM_MIRRORS)


def test_unit_literals_mirror_vocab():
    assert literal_values(enums.LengthUnit) == frozenset(VOCAB.length_units)
    assert literal_values(enums.TimeUnit) == frozenset(VOCAB.time_units)
    assert literal_values(enums.DoseUnit) - {"other"} == VOCAB.dose_units


def test_exposure_source_dose_units_are_known():
    for source in VOCAB.enum("exposure_sources"):
        allowed = VOCAB.dose_units_for_source(source)
        assert allowed <= VOCAB.dose_units | {"as_written"}, source


# ----- record model -----------------------------------------------------


def test_record_has_every_vocab_field():
    missing = set(VOCAB_PATHS) - set(RECORD_PATHS)
    assert not missing, f"FormulationRecord lacks vocab fields: {sorted(missing)}"


def test_record_extensions_are_declared():
    extra = set(RECORD_PATHS) - set(VOCAB_PATHS)
    assert extra == mapping.RECORD_EXTENSIONS


@pytest.mark.parametrize(
    "path", sorted(p for p, s in VOCAB_PATHS.items() if s.get("type") == "enum")
)
def test_record_enum_fields_match_vocab(path):
    expected = vocab_enum_values(VOCAB_PATHS[path]["values"])
    assert literal_values(RECORD_PATHS[path]) == expected


# ----- LLM models -------------------------------------------------------


def test_computed_fields_never_reach_the_llm():
    assert VOCAB.computed_fields <= set(mapping.LLM_EXCLUDED)


def test_mapping_keys_are_vocab_paths():
    unknown = (set(mapping.VOCAB_TO_LLM) | set(mapping.LLM_EXCLUDED)) - set(VOCAB_PATHS)
    assert not unknown, f"mapping.py references unknown vocab paths: {sorted(unknown)}"
    assert not set(mapping.VOCAB_TO_LLM) & set(mapping.LLM_EXCLUDED)


def test_every_vocab_field_is_covered_by_llm_schema():
    bad = {
        path: [t for t in mapping.llm_targets(path) if t not in LLM_PATHS] for path in VOCAB_PATHS
    }
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, f"vocab fields map to non-existent LLM fields: {bad}"


def test_every_llm_field_is_mapped_or_declared():
    targets = {t for p in VOCAB_PATHS for t in mapping.llm_targets(p)}
    orphan = set(LLM_PATHS) - targets - mapping.LLM_EXTENSIONS
    assert not orphan, f"LLM fields without a vocab mapping: {sorted(orphan)}"
    stale = mapping.LLM_EXTENSIONS - set(LLM_PATHS)
    assert not stale, f"LLM_EXTENSIONS lists missing fields: {sorted(stale)}"


@pytest.mark.parametrize(
    "path", sorted(p for p, s in VOCAB_PATHS.items() if s.get("type") == "enum")
)
def test_llm_enum_fields_match_vocab(path):
    expected = vocab_enum_values(VOCAB_PATHS[path]["values"])
    for target in mapping.llm_targets(path):
        tp = LLM_PATHS[target]
        if get_origin(tp) is Literal:
            assert literal_values(tp) == expected, target
