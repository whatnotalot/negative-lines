"""Full dataset record, a 1:1 mirror of ``vocab.yaml`` ``record`` (v3).

Built by code (enrichment step or gold-set adapter), never sent to an LLM.
Field names follow vocab.yaml exactly; fields that vocab.yaml does not define
are listed in ``schema/mapping.py`` ``RECORD_EXTENSIONS``.

Conventions (vocab): ``None`` = not stated, never 0. Raw values are stored as
printed; ``computed`` fields are filled by code only.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from negative_lines.schema import validators as v
from negative_lines.schema.enums import (
    AmountBasis,
    BakeMethod,
    ComplianceRule,
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


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Provenance(_Model):
    source_type: SourceType
    doc_id: str
    title: str | None = None
    assignee_or_authors: str | None = None
    year: int | None = None
    location: str | None = Field(None, description="e.g. 'Table 2, Example 3, p.14'")
    evidence_snippet: str | None = None
    is_comparative: bool = False
    extraction_model: str | None = Field(None, description="null for hand-labeled records")
    confidence: float | None = Field(None, ge=0, le=1, description="extraction agent's own score")
    human_verified: bool = False
    labeler_confidence: Confidence | None = None
    labeler_note: str | None = None
    # extension
    refs: list[SourceRef] = Field(default_factory=list)


class Polymer(_Model):
    repeat_units: str | None = None
    monomer_ratio: str | None = None
    mw: float | None = None
    pdi: float | None = None


class Component(_Model):
    role: Role
    role_other_text: str | None = None
    name_as_written: str
    definition_location: str | None = None
    name_resolved: str | None = None  # computed
    smiles: str | None = None  # computed
    cas: str | None = None  # computed
    pubchem_cid: int | None = None  # computed
    polymer: Polymer | None = None
    amount_raw: float | str | None = Field(
        None, description="string only for ranges or unparseable text"
    )
    amount_unit: str | None = None
    amount_basis: AmountBasis | None = None
    nonvolatile_content_pct: float | None = None
    mixture_id: str | None = None
    mixture_ratio: str | None = None
    amount_wt_pct_solids: float | None = None  # computed
    labeler_confidence: Confidence | None = None
    labeler_note: str | None = None
    # extension
    refs: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _rules(self) -> Component:
        v.raise_if(
            [
                v.check_other_text("role", self.role, self.role_other_text),
                v.check_low_confidence(
                    self.amount_basis == "unspecified" and self.labeler_confidence is not None,
                    "amount_basis 'unspecified'",
                    self.labeler_confidence,
                ),
            ]
        )
        return self


class SoftbakeStep(_Model):
    temp: float | str | None = None
    time: float | None = None
    time_unit: TimeUnit | None = None


class Exposure(_Model):
    source: ExposureSource | None = None
    mode: ExposureMode | None = None
    tool: str | None = None
    immersion: bool | None = None
    dose: float | None = None
    dose_unit: DoseUnit | None = None
    dose_type: DoseType | None = None
    dose_meter_wavelength_nm: float | None = None
    wavelength_min_nm: float | None = None
    intensity_mw_cm2: float | None = None
    exposure_time_s: float | None = None
    dose_computed: float | None = None  # computed: intensity_mw_cm2 x exposure_time_s
    ebeam_kv: float | None = None
    ion_species: str | None = None
    ion_energy_kev: float | None = None

    @model_validator(mode="after")
    def _rules(self) -> Exposure:
        v.raise_if(
            [
                v.check_dose_has_unit(self.dose, self.dose_unit),
                v.check_dose_unit(self.source, self.dose_unit),
            ]
        )
        return self


class Developer(_Model):
    name: str | None = None
    concentration: str | None = None
    time: float | None = None
    time_unit: TimeUnit | None = None
    temp: float | str | None = None
    method: DeveloperMethod | None = None


class Process(_Model):
    substrate: str | None = None
    primer: str | None = None
    underlayer: str | None = None
    coating_method: str | None = None
    film_thickness: float | None = None
    film_thickness_unit: LengthUnit | None = None
    thickness_stage: ThicknessStage | None = None
    softbake_steps: list[SoftbakeStep] = Field(default_factory=list)
    bake_method: BakeMethod | None = None
    exposure: Exposure = Field(default_factory=Exposure)
    peb_temp: float | str | None = None
    peb_time: float | None = None
    peb_time_unit: TimeUnit | None = None
    developer: Developer = Field(default_factory=Developer)
    rinse: str | None = None
    hardbake_temp: float | str | None = None
    hardbake_time: float | None = None
    hardbake_time_unit: TimeUnit | None = None
    # extension: refs per process group (coating, softbake, exposure, peb, development, hardbake)
    refs: dict[str, list[SourceRef]] = Field(default_factory=dict)


class Result(_Model):
    metric: Metric
    metric_as_written: str
    definition_as_written: str | None = None
    value: float | None = Field(None, description="null for figure-only evidence")
    value_qualitative: str | None = None
    scale: str | None = None
    unit: str | None = None
    sigma: int | None = None
    threshold_pct: float | None = None
    pitch_nm: float | None = None
    pattern_type: PatternType | None = None
    film_thickness: float | None = None
    position: str | None = None
    condition: str | None = None
    method: str | None = None
    reference_record_id: str | None = None
    labeler_confidence: Confidence | None = None
    labeler_note: str | None = None
    # extensions
    figure_only: bool = False
    refs: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _rules(self) -> Result:
        v.raise_if(
            [
                v.check_sigma(self.sigma),
                v.check_nonblank("metric_as_written", self.metric_as_written),
                v.check_not_digitized(self.value, self.figure_only),
            ]
        )
        return self


class ComplianceFlag(_Model):
    component_ref: str
    rule: ComplianceRule
    list_version_date: date | None = None
    rationale: str | None = None


class Compliance(_Model):
    flags: list[ComplianceFlag] = Field(default_factory=list)


class FormulationRecord(_Model):
    """One formulation, processed one way, with its results (dataset row)."""

    record_id: str = Field(description="<doc_id>_<example label>, e.g. 'JP2019123456A_cex1'")
    solids_content_wt_pct: float | None = None
    coating_only: bool = False
    source_conflict_note: str | None = None
    provenance: Provenance
    components: list[Component] = Field(default_factory=list)
    process: Process = Field(default_factory=Process)
    results: list[Result] = Field(default_factory=list)
    compliance: Compliance = Field(default_factory=Compliance)
    # extensions
    vocab_version: int | None = None
    warnings: list[str] = Field(default_factory=list)
