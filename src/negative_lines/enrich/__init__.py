"""Enrichment: LLM output -> dataset records (IDs, units, computed fields, provenance)."""

from negative_lines.enrich.amounts import compute_wt_pct_solids
from negative_lines.enrich.convert import merge_bake_method, primary_ref, to_formulation_record
from negative_lines.enrich.ids import example_slug, make_record_id, unique_id
from negative_lines.enrich.units import to_nm, to_seconds

__all__ = [
    "compute_wt_pct_solids",
    "example_slug",
    "make_record_id",
    "merge_bake_method",
    "primary_ref",
    "to_formulation_record",
    "to_nm",
    "to_seconds",
    "unique_id",
]
