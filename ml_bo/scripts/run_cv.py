"""Leave-one-out cross-validation of surrogates for every campaign objective.

Writes results/cv/predictions.csv and results/cv/metrics.csv.
Usage: python scripts/run_cv.py [--workers 16]
"""
from __future__ import annotations

import argparse
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

MODELS = ["additive", "additive+int", "ard", "rf", "mean"]


def _init():
    import torch
    torch.set_num_threads(1)
    warnings.filterwarnings("ignore")


def _run(key, obj_key, model):
    from neglines.bo import target_var
    from neglines.campaigns import get_campaign
    from neglines.gp import loo_baseline, loo_gp, transform_y

    c = get_campaign(key)
    obj = c.objective(obj_key)
    obs = c.observed
    X = c.encode(obs)
    y = transform_y(c.y(obj_key), obj.log)
    var = target_var(c, obj_key, obs)
    r = loo_gp(X, y, c.groups(), model, var) if model in ("additive", "additive+int", "ard") \
        else loo_baseline(X, y, model)
    preds = pd.DataFrame({"campaign": key, "objective": obj_key, "model": model,
                          "example_label": obs["example_label"].to_numpy(), "y": r.y, "mu": r.mu, "sd": r.sd,
                          "log_space": obj.log})
    return preds, {"campaign": key, "objective": obj_key, "model": model, "n": len(y), **r.metrics()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()
    from neglines.campaigns import all_campaigns
    from neglines.paths import RESULTS

    tasks = []
    for key, c in all_campaigns().items():
        keys = list(dict.fromkeys([o.key for o in c.objectives] + [c.scalar.key]))
        tasks += [(key, k, m) for k in keys for m in MODELS]
    with ProcessPoolExecutor(args.workers, initializer=_init) as ex:
        out = list(ex.map(_run, *zip(*tasks)))
    preds = pd.concat([p for p, _ in out], ignore_index=True)
    metrics = pd.DataFrame([m for _, m in out])
    d = RESULTS / "cv"
    d.mkdir(parents=True, exist_ok=True)
    preds.to_csv(d / "predictions.csv", index=False)
    metrics.to_csv(d / "metrics.csv", index=False)
    print(metrics.round(3).to_string())


if __name__ == "__main__":
    main()
