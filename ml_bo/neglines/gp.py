"""Small-data Gaussian process surrogates (BoTorch / GPyTorch).

Kernel choices:
  * additive:      sum over factor groups of RBF kernels (one lengthscale per group). For a one-hot
                   group this is a categorical kernel; with a family one-hot appended it becomes
                   hierarchical (same code > same family > different family).
  * additive+int:  additive plus a low-prior-weight ARD RBF over all dims for interactions.
  * ard:           single ARD RBF over all dims (the usual default, for comparison).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import torch
from botorch.fit import fit_gpytorch_mll
from botorch.models import ModelListGP, SingleTaskGP
from botorch.models.transforms import Standardize
from gpytorch.kernels import AdditiveKernel, RBFKernel, ScaleKernel
from gpytorch.mlls import ExactMarginalLogLikelihood
from gpytorch.priors import GammaPrior, LogNormalPrior

DTYPE = torch.double
KERNELS = ("additive", "additive+int", "ard")


def _t(x) -> torch.Tensor:
    return torch.as_tensor(np.asarray(x, float), dtype=DTYPE)


def make_kernel(groups: list[list[int]], kind: str = "additive"):
    d = max(max(g) for g in groups) + 1
    full = ScaleKernel(RBFKernel(ard_num_dims=d, lengthscale_prior=LogNormalPrior(0.5, 1.0)),
                       outputscale_prior=GammaPrior(2.0, 2.0))
    if kind == "ard":
        return full
    parts = [ScaleKernel(RBFKernel(active_dims=torch.tensor(g), lengthscale_prior=LogNormalPrior(0.0, 1.0)),
                         outputscale_prior=GammaPrior(2.0, 4.0)) for g in groups]
    if kind == "additive+int":
        parts.append(ScaleKernel(RBFKernel(ard_num_dims=d, lengthscale_prior=LogNormalPrior(0.5, 1.0)),
                                 outputscale_prior=GammaPrior(1.5, 8.0)))
    return AdditiveKernel(*parts)


def transform_y(y: np.ndarray, log: bool) -> np.ndarray:
    return np.log(np.asarray(y, float)) if log else np.asarray(y, float)


def fit_gp(X: np.ndarray, y: np.ndarray, groups, kind: str = "additive", yvar: np.ndarray | None = None,
           seed: int = 0) -> SingleTaskGP:
    """Fit a GP to (X, y) where y is already in model space. yvar (same space) fixes the noise."""
    torch.manual_seed(seed)
    tX, tY = _t(X), _t(y).reshape(-1, 1)
    kw = dict(covar_module=make_kernel(groups, kind), outcome_transform=Standardize(m=1))
    if yvar is not None:
        kw["train_Yvar"] = _t(yvar).reshape(-1, 1)
    model = SingleTaskGP(tX, tY, **kw)
    mll = ExactMarginalLogLikelihood(model.likelihood, model)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            fit_gpytorch_mll(mll)
        except Exception:  # keep prior-initialized hyperparameters if optimization fails
            pass
    model.eval()
    return model


def predict(model, X: np.ndarray, observation_noise: bool = False, batch: int = 4096):
    mus, sds = [], []
    with torch.no_grad(), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for i in range(0, len(X), batch):
            post = model.posterior(_t(X[i:i + batch]), observation_noise=observation_noise)
            mus.append(post.mean.squeeze(-1).numpy())
            sds.append(post.variance.clamp_min(1e-12).sqrt().squeeze(-1).numpy())
    return np.concatenate(mus), np.concatenate(sds)


def group_relevance(model, groups, names) -> dict[str, float]:
    """Outputscale share of each additive component (only for additive kernels)."""
    k = model.covar_module
    if not isinstance(k, AdditiveKernel):
        return {}
    scales = [float(sub.outputscale.detach()) for sub in k.kernels]
    labels = list(names) + (["interactions"] if len(scales) > len(names) else [])
    total = sum(scales)
    return {n: s / total for n, s in zip(labels, scales)}


@dataclass
class CVResult:
    y: np.ndarray
    mu: np.ndarray
    sd: np.ndarray          # predictive sd incl. noise, in model space

    def metrics(self) -> dict:
        y, mu, sd = self.y, self.mu, self.sd
        resid = y - mu
        ss_tot = np.sum((y - y.mean()) ** 2)
        from scipy.stats import norm, spearmanr
        rho = spearmanr(y, mu).statistic if np.std(mu) > 0 else np.nan
        return {
            "RMSE": float(np.sqrt(np.mean(resid ** 2))),
            "Q2": float(1 - np.sum(resid ** 2) / ss_tot) if ss_tot > 0 else np.nan,
            "Spearman": float(rho),
            "Coverage95": float(np.mean(np.abs(resid) <= 1.96 * sd)) if np.all(np.isfinite(sd)) else np.nan,
            "NLPD": float(-np.mean(norm.logpdf(y, mu, sd))) if np.all(sd > 0) else np.nan,
        }


def loo_gp(X, y, groups, kind="additive", yvar=None) -> CVResult:
    n = len(y)
    mu, sd = np.zeros(n), np.zeros(n)
    for i in range(n):
        m = np.arange(n) != i
        model = fit_gp(X[m], y[m], groups, kind, None if yvar is None else yvar[m])
        if yvar is None:
            a, b = predict(model, X[i:i + 1], observation_noise=True)
        else:
            a, b = predict(model, X[i:i + 1])
            b = np.sqrt(b ** 2 + yvar[i])
        mu[i], sd[i] = a[0], b[0]
    return CVResult(np.asarray(y, float), mu, sd)


def loo_baseline(X, y, kind: str) -> CVResult:
    n = len(y)
    mu, sd = np.zeros(n), np.zeros(n)
    for i in range(n):
        m = np.arange(n) != i
        if kind == "mean":
            mu[i], sd[i] = y[m].mean(), y[m].std(ddof=1)
        else:
            from sklearn.ensemble import RandomForestRegressor
            rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=1, random_state=0).fit(X[m], y[m])
            per_tree = np.array([t.predict(X[i:i + 1])[0] for t in rf.estimators_])
            mu[i], sd[i] = per_tree.mean(), max(per_tree.std(), 1e-6)
    return CVResult(np.asarray(y, float), mu, sd)


def model_list(models) -> ModelListGP:
    return ModelListGP(*models)
