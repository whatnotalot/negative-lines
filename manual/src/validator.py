"""
Manual Formulation Validator & Stoichiometry Calculator
Validates formulation recipes against vocab.yaml schema and semiconductor fab guidelines.
"""

def validate_manual_formulation(components):
    """
    Validates a manual formulation dictionary containing chemical loadings in grams.
    Expected keys:
      resin_amt: float
      primary_crosslinker_amt: float
      secondary_crosslinker_amt: float
      pag_amt: float
      quencher_amt: float
      solvent_1_amt: float
      solvent_2_amt: float
      surfactant_amt: float (optional)
    """
    errors = []
    warnings = []

    resin = float(components.get("resin_amt", 0.0))
    mm_xl = float(components.get("primary_crosslinker_amt", 0.0))
    cl_xl = float(components.get("secondary_crosslinker_amt", 0.0))
    pag = float(components.get("pag_amt", 0.0))
    quencher = float(components.get("quencher_amt", 0.0))
    solv1 = float(components.get("solvent_1_amt", 0.0))
    solv2 = float(components.get("solvent_2_amt", 0.0))
    surf = float(components.get("surfactant_amt", 0.0))

    if resin <= 0:
        errors.append("Resin mass must be greater than 0.0 g.")

    total_crosslinker = mm_xl + cl_xl
    if total_crosslinker <= 0:
        errors.append("Total crosslinker mass must be greater than 0.0 g.")
    elif mm_xl > 0 and cl_xl == 0:
        warnings.append("Single crosslinker (melamine only) detected. Prior patent data indicates high roughness (LWR > 10 nm).")
    elif cl_xl > 0 and mm_xl == 0:
        warnings.append("Single crosslinker (glycoluril only) detected. Prior patent data indicates severe roughness (LWR > 13 nm).")

    if pag <= 0:
        errors.append("Photoacid generator (PAG) mass must be greater than 0.0 g.")

    total_solids = resin + total_crosslinker + pag + quencher + surf
    total_solvents = solv1 + solv2
    total_mass = total_solids + total_solvents

    if total_solvents <= 0:
        errors.append("Solvent mass must be greater than 0.0 g to form spin-coatable solution.")

    solids_wt_percent = (total_solids / total_mass * 100.0) if total_mass > 0 else 0.0
    if solids_wt_percent < 3.0:
        warnings.append(f"Solids content ({solids_wt_percent:.1f} wt%) is very low. Target film thickness may fall below 100 nm.")
    elif solids_wt_percent > 25.0:
        warnings.append(f"Solids content ({solids_wt_percent:.1f} wt%) is high. High risk of poor spin uniformity or particle precipitation.")

    # Chemical Ratios
    pag_to_resin = (pag / resin * 100.0) if resin > 0 else 0.0
    quencher_to_pag = (quencher / pag * 100.0) if pag > 0 else 0.0
    xl_to_resin = (total_crosslinker / resin * 100.0) if resin > 0 else 0.0
    mm_ratio = (mm_xl / total_crosslinker * 100.0) if total_crosslinker > 0 else 0.0

    if pag_to_resin > 20.0:
        warnings.append(f"PAG loading ({pag_to_resin:.1f}% on resin) is elevated. Risk of optical opacity or phase segregation.")
    if quencher_to_pag > 30.0:
        warnings.append(f"Quencher loading ({quencher_to_pag:.1f}% on PAG) is high. May cause severe sensitivity loss (high dose required).")

    status = "VALID" if not errors else "INVALID"

    return {
        "status": status,
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "calculated_properties": {
            "total_solids_g": round(total_solids, 4),
            "total_solvents_g": round(total_solvents, 4),
            "total_mass_g": round(total_mass, 4),
            "solids_wt_percent": round(solids_wt_percent, 2),
            "crosslinker_to_resin_percent": round(xl_to_resin, 2),
            "mm_crosslinker_percent": round(mm_ratio, 1),
            "pag_to_resin_percent": round(pag_to_resin, 2),
            "quencher_to_pag_percent": round(quencher_to_pag, 2)
        }
    }
