"""Controlled vocabulary as static ``Literal`` types.

Mirror of ``vocab.yaml``; ``tests/test_vocab_consistency.py`` fails if they drift.
When vocab.yaml changes: bump ``VOCAB_VERSION`` and update the affected Literal.
"""

from __future__ import annotations

from typing import Literal

VOCAB_VERSION = 3

SourceType = Literal["patent", "paper", "datasheet", "thesis", "other"]

Confidence = Literal["high", "medium", "low"]
"""vocab: ``labeler_confidence``. Also used for the LLM's self-reported confidence."""

Role = Literal[
    "resin",
    "crosslinker",
    "pag",
    "acid_amplifier",
    "quencher",
    "sensitizer",
    "photoinitiator",
    "monomer",
    "metal_oxo_cluster",
    "solvent",
    "surfactant",
    "adhesion_promoter",
    "additive",
    "product",
    "other",
]

AmountBasis = Literal[
    "parts_per_100_resin",
    "wt_pct_solids",
    "wt_pct_total",
    "mol_pct_vs_pag",
    "mol_eq_vs_pag",
    "mmol_per_g_solids",
    "w_v_pct",
    "solvent_mass_ratio",
    "solvent_ratio_unspecified",
    "mass_g",
    "parts_by_mass",
    "ppm_unspecified",
    "unspecified",
]

ExposureSource = Literal[
    "g-line_436",
    "h-line_405",
    "i-line_365",
    "broadband_uv",
    "KrF_248",
    "ArF_193",
    "EUV_13.5",
    "ebeam",
    "ion_beam",
    "visible",
    "mixed_lines",
    "other",
]

ExposureMode = Literal[
    "contact",
    "proximity",
    "projection",
    "ebeam_direct_write",
    "interference",
    "other",
    "unspecified",
]

DoseType = Literal["nominal", "measured", "effective", "unspecified"]

ThicknessStage = Literal["as_coated", "after_development", "unspecified"]

BakeMethod = Literal["hot_plate", "oven", "unspecified"]

DeveloperMethod = Literal["puddle", "immersion", "spray", "unspecified"]

PatternType = Literal[
    "line_space",
    "isolated_line",
    "isolated_space",
    "dots",
    "pillars",
    "contact_holes",
    "other",
]

Metric = Literal[
    "dose_gel",
    "d50",
    "dose_sat",
    "sensitivity_esize",
    "sensitivity_unspecified",
    "contrast_gamma",
    "resolution_min_cd_nm",
    "ler_3sigma_nm",
    "lwr_3sigma_nm",
    "max_aspect_ratio",
    "swelling",
    "scum_residue",
    "adhesion",
    "pattern_collapse",
    "profile",
    "film_thickness_measured",
    "thickness_uniformity_pct",
    "coating_defects",
    "viscosity",
    "film_forming",
    "alkali_solubility",
    "chemical_resistance",
    "solvent_resistance",
    "pencil_hardness",
    "peeling",
    "edge_roughness_cd_loss",
    "thickness_loss",
    "other",
]

ComplianceRule = Literal[
    "OECD_PFAS_definition", "REACH_SVHC", "REACH_annex_XVII", "TSCA_PFAS", "other"
]

ReconciliationCause = Literal[
    "boundary",
    "basis",
    "metric_def",
    "unit",
    "missed",
    "typo",
    "guide_unclear",
    "source_conflict",
]

# ----- units (vocab: units.*) -------------------------------------------

LengthUnit = Literal["nm", "um", "µm", "angstrom", "Å"]
"""vocab: ``units.length.accepted`` keys."""

TimeUnit = Literal["s", "min", "h"]
"""vocab: ``units.time.accepted`` keys."""

DoseUnit = Literal["mJ/cm2", "uC/cm2", "pC/cm", "fC", "ions/cm2", "other"]
"""vocab: union of ``units.dose.families`` plus ``other`` (for ``as_written`` sources)."""

#: Maps each Literal alias to the vocab.yaml section it mirrors (used by tests).
VOCAB_ENUM_MIRRORS: dict[str, object] = {
    "source_types": SourceType,
    "labeler_confidence": Confidence,
    "roles": Role,
    "amount_bases": AmountBasis,
    "exposure_sources": ExposureSource,
    "exposure_modes": ExposureMode,
    "dose_types": DoseType,
    "thickness_stages": ThicknessStage,
    "bake_methods": BakeMethod,
    "developer_methods": DeveloperMethod,
    "pattern_types": PatternType,
    "metrics": Metric,
    "compliance_rules": ComplianceRule,
    "reconciliation_causes": ReconciliationCause,
}
