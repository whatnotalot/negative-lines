"""Bayesian optimization over campaigns: retrospective replay and prospective design.

Models are fit to the maximization target BoTorch expects: t(y) = -log(y) (or -y) for objectives
that are minimized, +log(y) (or +y) for objectives that are maximized.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from botorch.acquisition.analytic import LogExpectedImprovement
from botorch.acquisition.logei import qLogNoisyExpectedImprovement
from botorch.acquisition.multi_objective.logei import qLogNoisyExpectedHypervolumeImprovement
from botorch.sampling import SobolQMCNormalSampler

from .campaigns import Campaign
from .gp import fit_gp, model_list, predict
from .rls import hypervolume, reference_point

DEFAULT_KERNEL = "additive+int"


def _sign(c: Campaign, key: str) -> float:
    return 1.0 if c.objective(key).direction == "max" else -1.0


def to_target(c: Campaign, key: str, y) -> np.ndarray:
    y = np.asarray(y, float)
    return _sign(c, key) * (np.log(y) if c.objective(key).log else y)


def from_target(c: Campaign, key: str, t) -> np.ndarray:
    t = _sign(c, key) * np.asarray(t, float)
    return np.exp(t) if c.objective(key).log else t


def best_observed(c: Campaign, key: str, df: pd.DataFrame | None = None) -> float:
    v = (c.observed if df is None else df)[key].to_numpy(float)
    return float(np.nanmax(v) if c.objective(key).direction == "max" else np.nanmin(v))


def target_var(c: Campaign, key: str, df: pd.DataFrame) -> np.ndarray | None:
    col = c.yvar_cols.get(key)
    if col is None:
        return None
    var = df[col].to_numpy(float)
    if c.objective(key).log:
        var = var / np.maximum(df[key].to_numpy(float), 1e-9) ** 2   # delta method
    return var


def fit_objectives(c: Campaign, df: pd.DataFrame, keys, kind=DEFAULT_KERNEL, impute: dict | None = None):
    """One GP per key on rows of df. Failed rows get the imputed (worst) target value."""
    X = c.encode(df)
    models = []
    for k in keys:
        t = to_target(c, k, df[k])
        if impute is not None:
            t = np.where(np.isnan(t), impute[k], t)
        var = target_var(c, k, df)
        if var is not None:
            var = np.where(np.isnan(var), np.nanmedian(var), var)
        models.append(fit_gp(X, t, c.groups(), kind, var))
    return models, X


# ================================================================================================
# Retrospective replay over the patent's own example table
# ================================================================================================
@dataclass
class ReplayResult:
    campaign: str
    strategy: str
    mode: str
    seed: int
    order: list[int]
    trace: list[float]        # best-so-far scalar (min) or hypervolume fraction (max), per step


def min_space(c: Campaign, keys, df: pd.DataFrame) -> np.ndarray:
    """Objective values with maximized objectives negated, so every column is minimized."""
    return np.stack([-_sign(c, k) * df[k].to_numpy(float) for k in keys], 1)


def target_ref(c: Campaign, keys, df: pd.DataFrame, margin: float = 0.1) -> torch.Tensor:
    """Hypervolume reference point in model (maximization) space: just below the worst value."""
    t = np.stack([to_target(c, k, df[k]) for k in keys], 1)
    lo, hi = np.nanmin(t, 0), np.nanmax(t, 0)
    return torch.as_tensor(lo - margin * np.where(hi > lo, hi - lo, 1.0), dtype=torch.double)


def _scalar_best(c: Campaign, idx) -> float:
    vals = c.table.iloc[list(idx)][c.scalar.key].to_numpy(float)
    vals = vals[~np.isnan(vals)]
    if not len(vals):
        return np.nan
    return float(vals.max() if c.scalar.direction == "max" else vals.min())


def _hv_frac(c: Campaign, idx, ref, hv_all) -> float:
    Y = min_space(c, [o.key for o in c.objectives], c.table.iloc[list(idx)])
    return hypervolume(Y, ref) / hv_all if hv_all > 0 else np.nan


def replay(c: Campaign, strategy: str, mode: str = "scalar", seed: int = 0, n_init: int = 2,
           kind: str = DEFAULT_KERNEL, mc_samples: int = 128) -> ReplayResult:
    """strategy in {'bo', 'random', 'patent_order'}; mode in {'scalar', 'mo'}."""
    rng = np.random.default_rng(seed)
    n = len(c.table)
    keys = [c.scalar.key] if mode == "scalar" else [o.key for o in c.objectives]
    Yall = min_space(c, [o.key for o in c.objectives], c.table)
    ref = reference_point(Yall)
    hv_all = hypervolume(Yall, ref)

    if strategy == "patent_order":
        order = list(range(n))
    else:
        order = list(rng.permutation(n)[:n_init])
        if strategy == "random":
            rest = [i for i in rng.permutation(n) if i not in order]
            order += rest
        else:
            while len(order) < n:
                order.append(_bo_pick(c, order, keys, mode, kind, ref, mc_samples, rng))

    trace = [(_scalar_best(c, order[:k]) if mode == "scalar" else _hv_frac(c, order[:k], ref, hv_all))
             for k in range(1, n + 1)]
    return ReplayResult(c.key, strategy, mode, seed, order, trace)


def _bo_pick(c, chosen, keys, mode, kind, ref, mc_samples, rng) -> int:
    remaining = [i for i in range(len(c.table)) if i not in chosen]
    df = c.table.iloc[chosen]
    ok = ~df["failed"].to_numpy()
    if ok.sum() < 2 or len(remaining) == 1:
        return int(rng.choice(remaining))
    impute = {k: np.nanmin(to_target(c, k, df.loc[ok, k])) for k in keys}
    models, X = fit_objectives(c, df, keys, kind, impute)
    Xr = torch.as_tensor(c.encode(c.table.iloc[remaining]), dtype=torch.double)
    with torch.no_grad(), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if mode == "scalar":
            best = float(models[0].train_targets.max())
            best = float(models[0].outcome_transform.untransform(torch.tensor([[best]]))[0].max())
            acq = LogExpectedImprovement(models[0], best_f=best)
            vals = acq(Xr.unsqueeze(1))
        else:
            acq = qLogNoisyExpectedHypervolumeImprovement(
                model_list(models), ref_point=target_ref(c, keys, c.table),
                X_baseline=torch.as_tensor(X, dtype=torch.double),
                sampler=SobolQMCNormalSampler(torch.Size([mc_samples])), prune_baseline=True)
            vals = acq(Xr.unsqueeze(1))
    return int(remaining[int(torch.argmax(vals))])


def summarize_replays(results: list[ReplayResult], c: Campaign) -> pd.DataFrame:
    """Experiments needed to reach the pool optimum (scalar) or 95% of full hypervolume (mo)."""
    rows = []
    for r in results:
        tr = np.asarray(r.trace)
        if r.mode == "scalar":
            target = best_observed(c, c.scalar.key, c.table)
            hit = np.where(np.isclose(tr, target))[0]
        else:
            hit = np.where(tr >= 0.95)[0]
        rows.append({"strategy": r.strategy, "mode": r.mode, "seed": r.seed,
                     "experiments_to_target": int(hit[0]) + 1 if len(hit) else len(tr)})
    return pd.DataFrame(rows)


# ================================================================================================
# Prospective design over the candidate grid
# ================================================================================================
@dataclass
class Proposal:
    batch: pd.DataFrame        # proposed candidates with predictions + compliance + nearest neighbor
    candidates: pd.DataFrame   # all candidates with predictions (for plotting)
    n_excluded: int
    notes: list[str]


def _known_failure_levels(c: Campaign) -> dict[str, set]:
    """Categorical levels observed only in failed experiments."""
    out = {}
    if not c.table["failed"].any():
        return out
    for f in c.factors:
        if f.kind != "cat":
            continue
        good = set(c.observed[f.name])
        bad = set(c.table.loc[c.table["failed"], f.name]) - good
        if bad:
            out[f.name] = bad
    return out


def propose(c: Campaign, mode: str = "mo", q: int = 5, exclude_blocked: bool = False,
            penalty_weight: float = 0.5, swaps: dict | None = None, kind: str = DEFAULT_KERNEL,
            mc_samples: int = 128, seed: int = 0, prefilter: int = 600, screener=None) -> Proposal:
    torch.manual_seed(seed)
    notes = []
    keys = [c.scalar.key] if mode == "scalar" else [o.key for o in c.objectives]
    cand = c.candidates()
    Xc = c.encode(cand)
    Xo = c.encode(c.table)
    # drop already-tested candidates
    dist = np.abs(Xc[:, None, :] - Xo[None, :, :]).sum(-1)
    tested = dist.min(1) < 1e-9
    nn = dist.argmin(1)
    cand["nearest_record"] = c.table["example_label"].to_numpy()[nn]
    cand["nearest_distance"] = dist.min(1)
    # compliance (cached by component signature)
    cache, results = {}, []
    for _, row in cand.iterrows():
        sig = tuple(sorted((d["role"], d["name"]) for d in c.components_of(row)))
        if sig not in cache:
            cache[sig] = c.screen(pd.DataFrame([row]), swaps, screener)[0]
        results.append(cache[sig])
    cand["compliance"] = [r.summary() for r in results]
    cand["worst"] = [r.worst for r in results]
    cand["penalty"] = [r.penalty for r in results]
    cand["pfas"] = [r.pfas for r in results]
    # known failure regions
    fail = _known_failure_levels(c)
    risky = np.zeros(len(cand), bool)
    for name, levels in fail.items():
        risky |= cand[name].isin(levels).to_numpy()
        notes.append(f"Excluded {name} in {sorted(levels)}: only observed in failed experiments.")
    keep = ~tested & ~risky
    if exclude_blocked:
        keep &= cand["worst"].to_numpy() != "block"
    n_excluded = int((~keep).sum())

    impute = None
    if c.table["failed"].any():
        impute = {k: np.nanmin(to_target(c, k, c.observed[k])) for k in keys}
    models, X = fit_objectives(c, c.table if impute else c.observed, keys, kind, impute)
    for k, m in zip(keys, models):
        mu, sd = predict(m, Xc)
        cand[f"{k}_pred"] = from_target(c, k, mu)
        lo, hi = from_target(c, k, mu + 2 * sd), from_target(c, k, mu - 2 * sd)
        cand[f"{k}_lo"], cand[f"{k}_hi"] = np.minimum(lo, hi), np.maximum(lo, hi)
        cand[f"{k}_sd_model"] = sd
    if c.scalar.key not in keys and {"Eop", "LWR"} <= set(keys):
        cand["Z_pred"] = 16.0 ** 3 * cand["LWR_pred"] ** 2 * cand["Eop_pred"] * 1e-6
    if c.scalar.key not in keys and {"LER", "sensitivity", "resolution"} <= set(keys):
        cand["Z_pred"] = cand["resolution_pred"] ** 3 * cand["LER_pred"] ** 2 * cand["sensitivity_pred"] * 1e-6

    if keep.sum() == 0:
        notes.append("No candidates remain after the compliance and known-failure filters.")
        return Proposal(cand.iloc[:0], cand, n_excluded, notes)

    idx_keep = np.where(keep)[0]
    if len(idx_keep) > prefilter:
        # cheap pre-screen: standardized optimistic (UCB) target summed over objectives
        ucb = np.zeros(len(idx_keep))
        for k in keys:
            t = to_target(c, k, cand[f"{k}_pred"].to_numpy()[idx_keep])
            u = t + 2.0 * cand[f"{k}_sd_model"].to_numpy()[idx_keep]
            ucb += (u - u.mean()) / (u.std() + 1e-12)
        idx_keep = idx_keep[np.argsort(-ucb)[:prefilter]]
        notes.append(f"Acquisition evaluated on the top {prefilter} candidates by UCB pre-screen.")
    Xk = torch.as_tensor(Xc[idx_keep], dtype=torch.double)
    log_pen = np.log(np.clip(1 - penalty_weight * cand["penalty"].to_numpy()[idx_keep], 1e-12, 1))
    Xb = torch.as_tensor(X, dtype=torch.double)
    sampler = SobolQMCNormalSampler(torch.Size([mc_samples]))
    if mode == "scalar":
        acq = qLogNoisyExpectedImprovement(models[0], X_baseline=Xb, sampler=sampler)
    else:
        acq = qLogNoisyExpectedHypervolumeImprovement(model_list(models), ref_point=target_ref(c, keys, c.observed),
                                                      X_baseline=Xb, sampler=sampler, prune_baseline=True)
    chosen, acq_vals = [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for _ in range(min(q, len(idx_keep))):
            with torch.no_grad():
                vals = torch.cat([acq(Xk[i:i + 512].unsqueeze(1)) for i in range(0, len(Xk), 512)]).numpy()
            score = vals + log_pen
            score[chosen] = -np.inf
            j = int(np.argmax(score))
            chosen.append(j)
            acq_vals.append(float(score[j]))
            acq.set_X_pending(Xk[chosen])
    batch = cand.iloc[idx_keep[chosen]].copy()
    batch.insert(0, "rank", range(1, len(chosen) + 1))
    batch["log_acq"] = acq_vals
    return Proposal(batch.reset_index(drop=True), cand, n_excluded, notes)
