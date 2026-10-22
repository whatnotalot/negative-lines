"""LLM-facing structured-output schemas.

Two calls per document type:

1. ``DocumentMap``: one pass over the document (or per chunk) that lists
   examples, tables, codename definitions, shared conditions and grade scales.
2. ``ExampleExtraction``: one call per example, with the relevant context
   assembled by code, returning one or more ``LLMRecord``s.

These models follow the strict-schema rules in ``schema/base.py``. They
contain only what a labeler copies from the source: no computed fields, no
compliance flags, no pipeline metadata. ``schema/mapping.py`` documents how
each field maps to ``vocab.yaml`` / ``schema/record.py``.

Field descriptions are part of the prompt; keep them short and rule-bearing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from negative_lines.schema import validators as v
from negative_lines.schema.base import StrictLLMModel
from negative_lines.schema.enums import (
    AmountBasis,
    BakeMethod,
    Confidence,
    DeveloperMethod,
    DoseType,
    DoseUnit,
    ExposureMode,
    ExposureSource,
    LengthUnit,
    Metric,
    PatternType,
    Role,
    SourceType,
    ThicknessStage,
    TimeUnit,
)
from negative_lines.schema.refs import SourceRef

_NULL = "null if not stated."
_REFS = "Source references for these values; most specific block first. Add more refs when values come from several places (e.g. a codename defined elsewhere, a shared-conditions paragraph)."
_CONF = "Your confidence that these values are copied and classified correctly."
_NOTE = "Ambiguities, assumptions or the reason for low confidence. null if none."
_TEMP_V = "Temperature in °C as printed, if a single number. " + _NULL
_TEMP_T = "Temperature as text only if not a single number, e.g. 'RT' or '90-110 °C'. " + _NULL


def _has_values(model: StrictLLMModel, exclude: tuple[str, ...] = ("refs",)) -> bool:
    for name in type(model).model_fields:
        if name in exclude:
            continue
        val = getattr(model, name)
        if val not in (None, [], ""):
            return True
    return False


# =========================================================================
# Stage 1: document map
# =========================================================================


class DocumentInfo(StrictLLMModel):
    source_type: SourceType
    doc_id: str = Field(
        description="Publication number or DOI exactly as given, e.g. 'US20080241753A1'."
    )
    title: str | None = Field(description=_NULL)
    assignee_or_authors: str | None = Field(
        description="Assignee(s) or authors, as printed. " + _NULL
    )
    year: int | None = Field(description="Publication year. " + _NULL)
    language: str | None = Field(
        description="Language of the provided text (e.g. 'en'; 'en (machine translation)'). "
        + _NULL
    )


class ExampleEntry(StrictLLMModel):
    label: str = Field(
        description="Example label exactly as written, e.g. 'Example 3', 'Comparative Example 1', 'W1'."
    )
    is_comparative: bool
    block_ids: list[str] = Field(
        description="Blocks that describe this example's formulation or process."
    )
    table_ids: list[str] = Field(description="IDs of tables that contain data for this example.")
    has_results: bool = Field(description="True if any performance or coating result is reported.")
    note: str | None = Field(description=_NOTE)


class TableEntry(StrictLLMModel):
    table_id: str
    caption: str | None = Field(description=_NULL)
    content: Literal["composition", "process", "results", "mixed", "other"]
    examples_covered: list[str] = Field(description="Example labels that appear in this table.")


class CodenameDefinition(StrictLLMModel):
    codename: str = Field(description="Code as written, e.g. 'PAG-2', 'Resin A', 'B-1'.")
    definition_text: str = Field(
        description="The definition copied verbatim (name, structure description)."
    )
    refs: list[SourceRef]


class SharedCondition(StrictLLMModel):
    description: str = Field(
        description="What is shared, e.g. 'exposure and development conditions for all examples'."
    )
    applies_to: list[str] = Field(
        description="Example labels it applies to; ['all'] if stated for all examples."
    )
    refs: list[SourceRef]


class GradeScale(StrictLLMModel):
    scale_id: str = Field(description="Short id, e.g. 'adhesion', 'residue'.")
    scale_text: str = Field(
        description="Grade legend copied verbatim, e.g. '○: no residue; ×: residue'."
    )
    refs: list[SourceRef]


class DocumentMap(StrictLLMModel):
    """Inventory of a document before example-level extraction."""

    document: DocumentInfo
    examples: list[ExampleEntry] = Field(
        description="Every worked example and comparative example with concrete amounts. Exclude claim ranges."
    )
    tables: list[TableEntry]
    codename_definitions: list[CodenameDefinition]
    shared_conditions: list[SharedCondition]
    grade_scales: list[GradeScale]
    note: str | None = Field(description=_NOTE)


# =========================================================================
# Stage 2: example-level extraction
# =========================================================================


class LLMPolymer(StrictLLMModel):
    repeat_units: str | None = Field(
        description="Repeat units as text, e.g. 'hydroxystyrene / styrene'. " + _NULL
    )
    monomer_ratio: str | None = Field(description="Exactly as printed, e.g. '70/30 mol'. " + _NULL)
    mw: float | None = Field(description="Weight-average molecular weight as printed. " + _NULL)
    pdi: float | None = Field(description=_NULL)


class LLMComponent(StrictLLMModel):
    role: Role = Field(
        description="Role the source gives the ingredient; else the function it plays. 'product' only for commercial resists with unknown composition."
    )
    role_other_text: str | None = Field(description="Required if role is 'other'. " + _NULL)
    name_as_written: str = Field(
        description="Name or codename verbatim, e.g. 'PAG-2'. Do not resolve codenames."
    )
    definition_location: str | None = Field(
        description="Where a codename is defined, e.g. 'Synthesis Example 2, [0061]'. " + _NULL
    )
    polymer: LLMPolymer | None = Field(
        description="Only for resins/polymers with stated details. " + _NULL
    )
    amount_value: float | None = Field(
        description="Amount as printed, if a single number. Do not convert. " + _NULL
    )
    amount_text: str | None = Field(
        description="Amount as text only if not a single number (range, '<0.1'). " + _NULL
    )
    amount_unit: str | None = Field(
        description="Unit as printed, e.g. 'parts', 'wt%', 'g', 'mol%'. " + _NULL
    )
    amount_basis: AmountBasis | None = Field(
        description="What the amount is relative to. 'wt% relative to/based on resin' = parts_per_100_resin. Bare '%' = unspecified (confidence low). null only if no amount."
    )
    nonvolatile_content_pct: float | None = Field(
        description="For resins supplied as solutions: their solids %, amount then refers to the solution. "
        + _NULL
    )
    mixture_id: str | None = Field(
        description="Same id on components given as one mixture (e.g. 'PAG3+PAG4 10 parts total'). "
        + _NULL
    )
    mixture_ratio: str | None = Field(
        description="Ratio within the mixture as printed, e.g. '95:5'. " + _NULL
    )
    confidence: Confidence = Field(description=_CONF)
    note: str | None = Field(description=_NOTE)
    refs: list[SourceRef] = Field(description=_REFS)

    @model_validator(mode="after")
    def _rules(self) -> LLMComponent:
        has_amount = self.amount_value is not None or self.amount_text is not None
        v.raise_if(
            [
                v.check_other_text("role", self.role, self.role_other_text),
                v.check_value_xor_text("amount", self.amount_value, self.amount_text),
                v.check_amount_has_basis(has_amount, self.amount_basis),
                v.check_low_confidence(
                    self.amount_basis == "unspecified",
                    "amount_basis 'unspecified'",
                    self.confidence,
                ),
                v.check_fraction("nonvolatile_content_pct", self.nonvolatile_content_pct),
                v.check_refs_present(f"component {self.name_as_written!r}", self.refs),
            ]
        )
        return self


class LLMCoating(StrictLLMModel):
    substrate: str | None = Field(description="As written, e.g. 'Si wafer', 'PET'. " + _NULL)
    primer: str | None = Field(
        description="Separate primer step, e.g. 'HMDS', 'OmniCoat'. Not a component. " + _NULL
    )
    underlayer: str | None = Field(
        description="Organic underlayer with material, bake, thickness as written. " + _NULL
    )
    coating_method: str | None = Field(
        description="As written, e.g. 'spin coater 315 rpm 15 s'. " + _NULL
    )
    film_thickness: float | None = Field(
        description="Film thickness as printed (no conversion). " + _NULL
    )
    film_thickness_unit: LengthUnit | None = Field(description=_NULL)
    thickness_stage: ThicknessStage | None = Field(
        description="Whether thickness is as coated or after development. " + _NULL
    )
    refs: list[SourceRef] = Field(description=_REFS)

    @model_validator(mode="after")
    def _rules(self) -> LLMCoating:
        v.raise_if([v.check_refs_present("coating", self.refs, _has_values(self))])
        return self


class LLMBakeStep(StrictLLMModel):
    temp_value: float | None = Field(description=_TEMP_V)
    temp_text: str | None = Field(description=_TEMP_T)
    time: float | None = Field(description="Time as printed. " + _NULL)
    time_unit: TimeUnit | None = Field(description=_NULL)

    @model_validator(mode="after")
    def _rules(self) -> LLMBakeStep:
        v.raise_if([v.check_value_xor_text("temp", self.temp_value, self.temp_text)])
        return self


class LLMSoftbake(StrictLLMModel):
    """Soft bake / prebake / PAB / PB."""

    steps: list[LLMBakeStep] = Field(
        description="In order; a two-step bake (65 then 95 °C) is two steps."
    )
    method: BakeMethod | None = Field(description="hot_plate or oven if stated. " + _NULL)
    refs: list[SourceRef] = Field(description=_REFS)

    @model_validator(mode="after")
    def _rules(self) -> LLMSoftbake:
        v.raise_if([v.check_refs_present("softbake", self.refs, _has_values(self))])
        return self


class LLMBake(StrictLLMModel):
    """A single bake (post-exposure bake or hard bake)."""

    temp_value: float | None = Field(description=_TEMP_V)
    temp_text: str | None = Field(description=_TEMP_T)
    time: float | None = Field(description="Time as printed. " + _NULL)
    time_unit: TimeUnit | None = Field(description=_NULL)
    method: BakeMethod | None = Field(description="hot_plate or oven if stated. " + _NULL)
    refs: list[SourceRef] = Field(description=_REFS)

    @model_validator(mode="after")
    def _rules(self) -> LLMBake:
        v.raise_if(
            [
                v.check_value_xor_text("temp", self.temp_value, self.temp_text),
                v.check_refs_present("bake", self.refs, _has_values(self)),
            ]
        )
        return self


class LLMExposure(StrictLLMModel):
    source: ExposureSource | None = Field(description=_NULL)
    mode: ExposureMode | None = Field(description=_NULL)
    tool: str | None = Field(
        description="Tool or lamp as written; for mixed_lines list the lines. " + _NULL
    )
    immersion: bool | None = Field(description="ArF only: immersion or dry. " + _NULL)
    dose: float | None = Field(
        description="Dose as printed. null if only intensity and time are given (code multiplies). This is the process dose, not a sensitivity result."
    )
    dose_unit: DoseUnit | None = Field(
        description="Never convert between families (mJ/cm2 vs uC/cm2). 'other': copy the printed unit into note. "
        + _NULL
    )
    dose_type: DoseType | None = Field(description=_NULL)
    dose_meter_wavelength_nm: float | None = Field(
        description="Wavelength the dose was metered at (broadband). " + _NULL
    )
    wavelength_min_nm: float | None = Field(
        description="Cut-off filter, e.g. 480 for '480 nm or more'. " + _NULL
    )
    intensity_mw_cm2: float | None = Field(description="Intensity in mW/cm2 as printed. " + _NULL)
    exposure_time: float | None = Field(description="Exposure time as printed. " + _NULL)
    exposure_time_unit: TimeUnit | None = Field(description=_NULL)
    ebeam_kv: float | None = Field(description="Acceleration voltage for e-beam. " + _NULL)
    ion_species: str | None = Field(description=_NULL)
    ion_energy_kev: float | None = Field(description=_NULL)
    refs: list[SourceRef] = Field(description=_REFS)

    @model_validator(mode="after")
    def _rules(self) -> LLMExposure:
        v.raise_if(
            [
                v.check_dose_has_unit(self.dose, self.dose_unit),
                v.check_dose_unit(self.source, self.dose_unit),
                v.check_refs_present("exposure", self.refs, _has_values(self)),
            ]
        )
        return self


class LLMDevelopment(StrictLLMModel):
    developer_name: str | None = Field(
        description="As written, e.g. 'TMAH', 'PGMEA', 'SU-8 developer'. " + _NULL
    )
    concentration: str | None = Field(
        description="Copy as printed, e.g. '2.38 wt%' or '0.26 N'. " + _NULL
    )
    time: float | None = Field(description="Development time as printed. " + _NULL)
    time_unit: TimeUnit | None = Field(description=_NULL)
    temp_value: float | None = Field(description=_TEMP_V)
    temp_text: str | None = Field(description=_TEMP_T)
    method: DeveloperMethod | None = Field(description=_NULL)
    rinse: str | None = Field(description="Rinse as written, e.g. 'DI water 30 s'. " + _NULL)
    refs: list[SourceRef] = Field(description=_REFS)

    @model_validator(mode="after")
    def _rules(self) -> LLMDevelopment:
        v.raise_if(
            [
                v.check_value_xor_text("developer temp", self.temp_value, self.temp_text),
                v.check_refs_present("development", self.refs, _has_values(self)),
            ]
        )
        return self


class LLMProcess(StrictLLMModel):
    """Process conditions grouped so that each group carries its own references.

    Copy conditions stated once for several examples into each record and cite
    the shared block with purpose 'shared_condition'.
    """

    coating: LLMCoating | None = Field(description=_NULL)
    softbake: LLMSoftbake | None = Field(description=_NULL)
    exposure: LLMExposure | None = Field(description=_NULL)
    peb: LLMBake | None = Field(description="Post-exposure bake. " + _NULL)
    development: LLMDevelopment | None = Field(description=_NULL)
    hardbake: LLMBake | None = Field(description="Hard bake / cure after development. " + _NULL)


class LLMResult(StrictLLMModel):
    metric: Metric = Field(
        description="Metric the source actually measured (use its definition, not the word: E0 can be a gel dose)."
    )
    metric_as_written: str = Field(
        description="Metric name/wording verbatim, e.g. 'sensitivity (Eop)'."
    )
    definition_as_written: str | None = Field(
        description="Definition or formula if given (e.g. contrast). " + _NULL
    )
    value: float | None = Field(
        description="Numeric value as printed. null for qualitative or figure-only."
    )
    value_qualitative: str | None = Field(
        description="Grade symbol or relative value as printed, e.g. 'A', '○', '1.2x'. " + _NULL
    )
    scale: str | None = Field(description="The source's grade legend for this metric. " + _NULL)
    unit: str | None = Field(description="Unit as printed. " + _NULL)
    sigma: int | None = Field(description="1 or 3, for LER/LWR as reported. " + _NULL)
    threshold_pct: float | None = Field(
        description="For dose_sat: remaining-thickness %, e.g. 90. " + _NULL
    )
    pitch_value: float | None = Field(
        description="Pitch as printed, for resolution or Esize. " + _NULL
    )
    pitch_unit: LengthUnit | None = Field(description=_NULL)
    pattern_type: PatternType | None = Field(description=_NULL)
    film_thickness: float | None = Field(
        description="Film thickness this result refers to, as printed. " + _NULL
    )
    film_thickness_unit: LengthUnit | None = Field(description=_NULL)
    position: str | None = Field(
        description="Measurement position, e.g. 'Center', 'Edges'. " + _NULL
    )
    condition: str | None = Field(
        description="Conditions, e.g. 'smallest tested', target CD for Esize, 'CD vs half-pitch'. "
        + _NULL
    )
    method: str | None = Field(description="Measurement method/tool. " + _NULL)
    reference_example_label: str | None = Field(
        description="For relative values: the example they are relative to. " + _NULL
    )
    figure_only: bool = Field(
        description="True if only a figure shows it; then value must be null. Never read values off plots. A number stated in text or a caption is not figure-only."
    )
    confidence: Confidence = Field(description=_CONF)
    note: str | None = Field(description=_NOTE)
    refs: list[SourceRef] = Field(description=_REFS)

    @model_validator(mode="after")
    def _rules(self) -> LLMResult:
        v.raise_if(
            [
                v.check_nonblank("metric_as_written", self.metric_as_written),
                v.check_not_digitized(self.value, self.figure_only),
                v.check_low_confidence(
                    self.metric == "sensitivity_unspecified",
                    "metric 'sensitivity_unspecified'",
                    self.confidence,
                ),
                v.check_sigma(self.sigma),
                v.check_result_has_evidence(self.value, self.value_qualitative, self.figure_only),
                v.check_fraction("threshold_pct", self.threshold_pct),
                v.check_refs_present(f"result {self.metric_as_written!r}", self.refs),
            ]
        )
        return self


class LLMRecord(StrictLLMModel):
    """One formulation, processed one way, with its results."""

    example_label: str = Field(description="Example label exactly as in the document map.")
    variant_label: str | None = Field(
        description="Distinguishes several records of one example, e.g. 'dose 30 mJ/cm2'. null if only one."
    )
    is_comparative: bool
    coating_only: bool = Field(
        description="True if the source reports no exposure/development (coating data only)."
    )
    solids_content_wt_pct: float | None = Field(
        description="Solution solids content, e.g. 30 for 'dissolved to 30 wt% solids'. Not a component amount. "
        + _NULL
    )
    source_conflict_note: str | None = Field(
        description="Where the source contradicts itself and which value was recorded. " + _NULL
    )
    components: list[LLMComponent] = Field(
        description="Every ingredient; mixed solvents as one component each."
    )
    process: LLMProcess
    results: list[LLMResult]
    confidence: Confidence = Field(description="Overall confidence for this record.")
    note: str | None = Field(description=_NOTE)
    refs: list[SourceRef] = Field(
        description="Main evidence for the record as a whole (example heading or table row)."
    )

    @model_validator(mode="after")
    def _rules(self) -> LLMRecord:
        v.raise_if(
            [
                v.check_fraction("solids_content_wt_pct", self.solids_content_wt_pct),
                None if self.components else "record has no components",
            ]
        )
        return self

    def warnings(self) -> list[str]:
        return v.collect_warnings(self)


class ExampleExtraction(StrictLLMModel):
    """All records for one example."""

    example_label: str
    records: list[LLMRecord] = Field(
        description="Usually one. Several only if the same formulation is processed differently (e.g. several doses with results each)."
    )
    note: str | None = Field(description=_NOTE)


LLM_SCHEMAS: tuple[type[StrictLLMModel], ...] = (DocumentMap, ExampleExtraction)
"""Top-level models passed to ``with_structured_output``."""
