"""
Manual Lithography Calculator
Provides classical empirical estimations for film thickness, spin coating speed, and baseline dose.
"""

import math

def estimate_film_thickness(solids_wt_percent, spin_rpm=1500, k_factor=115.0):
    """
    Estimates resist film thickness using Meyerhofer's spin coating equation:
    Thickness (nm) ≈ k * (Solids_wt%)^1.4 / sqrt(spin_rpm)
    k_factor calibrated for typical PGMEA / phenolic novolac resist solutions (~115).
    """
    if solids_wt_percent <= 0 or spin_rpm <= 0:
        return 0.0
    
    thickness_nm = k_factor * (solids_wt_percent ** 1.38) / math.sqrt(spin_rpm / 1000.0)
    return round(thickness_nm, 1)

def estimate_baseline_sensitivity(pag_to_resin_percent, quencher_to_pag_percent, exposure_energy_kev=50.0):
    """
    Estimates baseline 50 keV electron-beam dose (uC/cm2) based on acid generator and quencher ratios.
    Empirically centered on US7432034B2 reference baselines (approx 5.0 - 6.5 uC/cm2).
    """
    base_dose = 5.2
    # Higher PAG increases sensitivity (lowers dose required)
    pag_effect = -0.12 * (pag_to_resin_percent - 7.0)
    # Higher quencher neutralizes acid, requiring higher dose
    quencher_effect = 0.08 * (quencher_to_pag_percent - 10.0)
    
    est_dose = max(2.5, min(15.0, base_dose + pag_effect + quencher_effect))
    return round(est_dose, 1)
