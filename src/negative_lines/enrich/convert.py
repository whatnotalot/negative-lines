"""``LLMRecord`` (+ document info) -> ``FormulationRecord`` (vocab v3 record).

Follows ``schema/mapping.py``. Rules marked PROVISIONAL are open team
decisions and are isolated in small functions so they are easy to change:

- ``merge_bake_method``: one vocab ``bake_method`` from per-bake methods.
- ``primary_ref``: which ref fills ``provenance.location`` / ``evidence_snippet``.
- ``is_comparative``: the record's value wins over the document map's, with a warning.
- ``provenance.confidence`` stays null until quote verification exists; the
  LLM's categorical confidence goes to ``labeler_confidence`` (per mapping.py).
"""

from __future__ import annotations

from collections.abc import Callable

from negative_lines.enrich.amounts import compute_wt_pct_solids
from negative_lines.enrich.units import to_nm, to_seconds
from negative_lines.schema.enums import VOCAB_VERSION
from negative_lines.schema.llm import DocumentInfo, LLMBake, LLMRecord
from negative_lines.schema.record import (
    Component,
    Developer,
    Exposure,
    FormulationRecord,
    Polymer,
    Process,
    Provenance,
    Result,
    SoftbakeStep,
)
from negative_lines.schema.refs import SourceRef


def _value_or_text(value: float | None, text: str | None) -> float | str | None:
    return value if value is not None else text


def merge_bake_method(*methods: str | None) -> tuple[str | None, str | None]:
    """PROVISIONAL. Returns (bake_method, warning)."""
    stated = [m for m in methods if m is not None]
    specific = sorted({m for m in stated if m != "unspecified"})
    if len(specific) == 1:
        return specific[0], None
    if len(specific) > 1:
        return None, f"bake methods differ between bakes {specific}: bake_method left null"
    return ("unspecified" if stated else None), None


def primary_ref(refs: list[SourceRef]) -> SourceRef | None:
    """PROVISIONAL. First ref with purpose 'value', else the first ref."""
    for r in refs:
        if r.purpose == "value":
            return r
    return refs[0] if refs else None


def _bake(b: LLMBake | None) -> tuple[float | str | None, float | None, str | None]:
    if b is None:
        return None, None, None
    return _value_or_text(b.temp_value, b.temp_text), b.time, b.time_unit


def _process(rec: LLMRecord, warn: list[str]) -> Process:
    p = rec.process
    c, sb, e, peb, dev, hb = p.coating, p.softbake, p.exposure, p.peb, p.development, p.hardbake

    bake_method, w = merge_bake_method(
        sb.method if sb else None, peb.method if peb else None, hb.method if hb else None
    )
    if w:
        warn.append(w)

    exposure = Exposure()
    if e is not None:
        time_s = to_seconds(e.exposure_time, e.exposure_time_unit)
        exposure = Exposure(
            source=e.source,
            mode=e.mode,
            tool=e.tool,
            immersion=e.immersion,
            dose=e.dose,
            dose_unit=e.dose_unit,
            dose_type=e.dose_type,
            dose_meter_wavelength_nm=e.dose_meter_wavelength_nm,
            wavelength_min_nm=e.wavelength_min_nm,
            intensity_mw_cm2=e.intensity_mw_cm2,
            exposure_time_s=time_s,
            dose_computed=(
                round(e.intensity_mw_cm2 * time_s, 9)
                if e.intensity_mw_cm2 is not None and time_s is not None
                else None
            ),
            ebeam_kv=e.ebeam_kv,
            ion_species=e.ion_species,
            ion_energy_kev=e.ion_energy_kev,
        )

    peb_temp, peb_time, peb_unit = _bake(peb)
    hb_temp, hb_time, hb_unit = _bake(hb)
    groups = {"coating": c, "softbake": sb, "exposure": e, "peb": peb, "development": dev,
              "hardbake": hb}  # fmt: skip
    return Process(
        substrate=c.substrate if c else None,
        primer=c.primer if c else None,
        underlayer=c.underlayer if c else None,
        coating_method=c.coating_method if c else None,
        film_thickness=c.film_thickness if c else None,
        film_thickness_unit=c.film_thickness_unit if c else None,
        thickness_stage=c.thickness_stage if c else None,
        softbake_steps=[
            SoftbakeStep(
                temp=_value_or_text(s.temp_value, s.temp_text), time=s.time, time_unit=s.time_unit
            )  # fmt: skip
            for s in (sb.steps if sb else [])
        ],
        bake_method=bake_method,
        exposure=exposure,
        peb_temp=peb_temp,
        peb_time=peb_time,
        peb_time_unit=peb_unit,
        developer=Developer(
            name=dev.developer_name,
            concentration=dev.concentration,
            time=dev.time,
            time_unit=dev.time_unit,
            temp=_value_or_text(dev.temp_value, dev.temp_text),
            method=dev.method,
        )
        if dev
        else Developer(),
        rinse=dev.rinse if dev else None,
        hardbake_temp=hb_temp,
        hardbake_time=hb_time,
        hardbake_time_unit=hb_unit,
        refs={name: g.refs for name, g in groups.items() if g is not None and g.refs},
    )


def to_formulation_record(
    rec: LLMRecord,
    *,
    document: DocumentInfo,
    record_id: str,
    extraction_model: str | None,
    map_is_comparative: bool | None = None,
    resolve_example: Callable[[str], str] | None = None,
) -> FormulationRecord:
    """Build the dataset record. ``resolve_example`` maps an example label to a record_id."""
    warn: list[str] = list(rec.warnings())

    if map_is_comparative is not None and map_is_comparative != rec.is_comparative:
        warn.append(
            f"is_comparative differs: document map {map_is_comparative}, record "
            f"{rec.is_comparative}; record value kept"
        )

    wt_pct, w = compute_wt_pct_solids(rec.components)
    warn += w
    components = [
        Component(
            role=c.role,
            role_other_text=c.role_other_text,
            name_as_written=c.name_as_written,
            definition_location=c.definition_location,
            polymer=Polymer(**c.polymer.model_dump()) if c.polymer else None,
            amount_raw=_value_or_text(c.amount_value, c.amount_text),
            amount_unit=c.amount_unit,
            amount_basis=c.amount_basis,
            nonvolatile_content_pct=c.nonvolatile_content_pct,
            mixture_id=c.mixture_id,
            mixture_ratio=c.mixture_ratio,
            amount_wt_pct_solids=wt_pct[i],
            labeler_confidence=c.confidence,
            labeler_note=c.note,
            refs=c.refs,
        )
        for i, c in enumerate(rec.components)
    ]

    results = []
    for i, r in enumerate(rec.results):
        if r.film_thickness is not None and r.film_thickness_unit is None:
            warn.append(f"results[{i}]: film_thickness without unit, not converted to nm")
        if r.pitch_value is not None and r.pitch_unit is None:
            warn.append(f"results[{i}]: pitch without unit, not converted to nm")
        ref_id = None
        if r.reference_example_label:
            ref_id = (
                resolve_example(r.reference_example_label)
                if resolve_example
                else r.reference_example_label
            )
        results.append(
            Result(
                metric=r.metric,
                metric_as_written=r.metric_as_written,
                definition_as_written=r.definition_as_written,
                value=r.value,
                value_qualitative=r.value_qualitative,
                scale=r.scale,
                unit=r.unit,
                sigma=r.sigma,
                threshold_pct=r.threshold_pct,
                pitch_nm=to_nm(r.pitch_value, r.pitch_unit),
                pattern_type=r.pattern_type,
                film_thickness=to_nm(r.film_thickness, r.film_thickness_unit),
                position=r.position,
                condition=r.condition,
                method=r.method,
                reference_record_id=ref_id,
                labeler_confidence=r.confidence,
                labeler_note=r.note,
                figure_only=r.figure_only,
                refs=r.refs,
            )
        )

    ref = primary_ref(rec.refs)
    provenance = Provenance(
        source_type=document.source_type,
        doc_id=document.doc_id,
        title=document.title,
        assignee_or_authors=document.assignee_or_authors,
        year=document.year,
        location=ref.location if ref else None,
        evidence_snippet=ref.quote if ref else None,
        is_comparative=rec.is_comparative,
        extraction_model=extraction_model,
        confidence=None,
        human_verified=False,
        labeler_confidence=rec.confidence,
        labeler_note=rec.note,
        refs=rec.refs,
    )

    process = _process(rec, warn)
    return FormulationRecord(
        record_id=record_id,
        solids_content_wt_pct=rec.solids_content_wt_pct,
        coating_only=rec.coating_only,
        source_conflict_note=rec.source_conflict_note,
        provenance=provenance,
        components=components,
        process=process,
        results=results,
        vocab_version=VOCAB_VERSION,
        warnings=warn,
    )
