"""Resolution-LER-sensitivity (RLS) trade-off utilities.

Z-factor (Wallow et al., Proc. SPIE 6921, 2008): Z = HP^3 x LER^2 x dose. With HP and LER in nm and
dose per cm^2, Z = HP^3 * LER^2 * dose * 1e-14 in [dose unit]·nm^3. Lower is better. It is only
comparable within one dose family (photon mJ/cm^2 vs electron µC/cm^2).
"""
from __future__ import annotations

import numpy as np


def z_factor(hp_nm, roughness_nm, dose):
    """Z in units of 1e-8 [dose]·nm^3 (the scale used in the literature)."""
    return np.asarray(hp_nm, float) ** 3 * np.asarray(roughness_nm, float) ** 2 * np.asarray(dose, float) * 1e-6


def pareto_mask(Y: np.ndarray) -> np.ndarray:
    """Non-dominated rows of Y under minimization of every column. NaN rows are never on the front."""
    Y = np.asarray(Y, float)
    ok = ~np.isnan(Y).any(1)
    mask = np.zeros(len(Y), bool)
    idx = np.where(ok)[0]
    for i in idx:
        others = Y[idx]
        dominated = np.any(np.all(others <= Y[i], 1) & np.any(others < Y[i], 1))
        mask[i] = not dominated
    return mask


def hypervolume(Y: np.ndarray, ref: np.ndarray) -> float:
    """Dominated hypervolume for minimization, bounded by ref (worse than every point)."""
    import torch
    from botorch.utils.multi_objective.hypervolume import Hypervolume

    Y = np.asarray(Y, float)
    Y = Y[~np.isnan(Y).any(1)]
    Y = Y[np.all(Y < ref, 1)]
    if len(Y) == 0:
        return 0.0
    hv = Hypervolume(ref_point=-torch.as_tensor(ref, dtype=torch.double))
    front = -torch.as_tensor(Y[pareto_mask(Y)], dtype=torch.double)
    return float(hv.compute(front))


def reference_point(Y: np.ndarray, margin: float = 0.1) -> np.ndarray:
    Y = np.asarray(Y, float)
    lo, hi = np.nanmin(Y, 0), np.nanmax(Y, 0)
    return hi + margin * np.where(hi > lo, hi - lo, np.abs(hi) + 1e-9)
