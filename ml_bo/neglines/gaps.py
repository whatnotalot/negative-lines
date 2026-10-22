"""Data-gap analysis shared by the app and the design agent."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import GoldSet


def pag_states(g: GoldSet, comp: pd.DataFrame) -> pd.DataFrame:
    """Per record: exposure family and the compliance state of its PAG."""
    pag_rec = set(g.components.loc[g.components.role == "pag", "record_id"])
    r = g.records.set_index("record_id")[["exposure_family", "doc_id"]].join(
        comp[["pfas_pag", "pag_unverified", "pag_worst"]])
    r["pag_state"] = np.select([~r.index.isin(pag_rec), r.pfas_pag.fillna(False).astype(bool),
                                r.pag_unverified.fillna(False).astype(bool), r.pag_worst == "watch"],
                               ["no PAG listed", "block", "unverified", "watch"], "clear")
    return r


def extraction_worklist(g: GoldSet, comp: pd.DataFrame) -> pd.DataFrame:
    r = pag_states(g, comp)
    euv_n = int((r.exposure_family == "EUV").sum())
    euv_block = int(((r.exposure_family == "EUV") & (r.pag_state == "block")).sum())
    fuji_unv = sorted(set(g.components[(g.components.record_id.str.startswith("US7432034B2")) &
                                       (g.components.role == "pag")].name) - {"I-1", "PAG4-36"})
    n_comp_numeric = int(g.records[g.records.is_comparative & g.records.record_id.isin(
        g.results.loc[g.results.value_num.notna(), "record_id"])].shape[0])
    return pd.DataFrame([
        {"priority": 1, "gap": "No PFAS-free PAG at EUV",
         "evidence": f"{euv_block} of {euv_n} EUV records use flagged PAGs; the PFAS-free EUV design space is empty",
         "extract": "EUV negative-tone patents with non-fluorinated onium salts or metal-oxo (tin-oxo) resists, "
                    "with Eop, LWR and resolution",
         "query": '"EUV" AND ("negative tone" OR "negative-tone") AND ("camphorsulfonate" OR "metal oxide" '
                  'OR "tin oxo" OR "non-fluorinated photoacid")'},
        {"priority": 1, "gap": "PAG structures missing",
         "evidence": f"{len(fuji_unv)} US7432034B2 PAG codes are unverified: {', '.join(fuji_unv)}",
         "extract": "Draw-to-SMILES for each code from the patent's structure lists; fills `smiles` and enables "
                    "the anion descriptors", "query": "US7432034B2 specification, compound lists I, II, III, J, PAG3, PAG4"},
        {"priority": 2, "gap": "Fluorosurfactant swap untested in litho resists",
         "evidence": "Silicone surfactants match fluorosurfactants only in WO2004107052A1 slit coating",
         "extract": "Examples reporting LER/defects with silicone vs fluorinated surfactants in CARs",
         "query": '"photoresist" AND "surfactant" AND ("silicone" OR "polysiloxane") AND ("fluorine-free" OR "PFAS-free")'},
        {"priority": 2, "gap": "No process sweeps",
         "evidence": "PEB, thickness and developer time are constant inside every litho campaign",
         "extract": "Papers with dose/PEB/thickness matrices (process-window studies)",
         "query": '"negative resist" AND ("PEB temperature" OR "post-exposure bake") AND ("process window" OR "dose latitude")'},
        {"priority": 3, "gap": "Non-phthalate plasticizer for thick SU-8",
         "evidence": "The crack-reducing SU-8 modification relies on DOP (likely DEHP)",
         "extract": "SU-8 / epoxy resist formulations with citrate, DINCH or polymeric plasticizers and crack/stress data",
         "query": '"SU-8" AND ("plasticizer" OR "flexibilizer") AND ("crack" OR "stress")'},
        {"priority": 3, "gap": "Few failures with numbers",
         "evidence": f"Only {n_comp_numeric} comparative examples carry a numeric result",
         "extract": "Prefer sources with comparative examples and numeric outcomes; they carry most of the signal",
         "query": '"comparative example" AND ("LWR" OR "LER") AND "negative"'},
    ])
