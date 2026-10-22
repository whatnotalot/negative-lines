"""Retrospective BO benchmark: would BO have found each patent's best example sooner?

Writes results/replay/traces.csv and results/replay/summary.csv.
Usage: python scripts/run_replay.py [--seeds 30] [--random-seeds 300] [--workers 20]
"""
from __future__ import annotations

import argparse
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

JOBS = [("euv", "scalar"), ("euv", "mo"), ("ebeam", "scalar"), ("ebeam", "mo"), ("su8", "scalar")]


def _init():
    import torch
    torch.set_num_threads(1)
    warnings.filterwarnings("ignore")


def _run(key, mode, strategy, seed):
    from neglines.bo import replay
    from neglines.campaigns import get_campaign

    c = get_campaign(key)
    r = replay(c, strategy, mode, seed=seed)
    labels = c.table["example_label"].tolist()
    return [{"campaign": key, "mode": mode, "strategy": strategy, "seed": seed, "step": i + 1,
             "value": v, "picked": labels[r.order[i]], "picked_index": int(r.order[i])}
            for i, v in enumerate(r.trace)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--random-seeds", type=int, default=300)
    ap.add_argument("--workers", type=int, default=20)
    args = ap.parse_args()

    from neglines.bo import ReplayResult, summarize_replays
    from neglines.campaigns import get_campaign
    from neglines.paths import RESULTS

    tasks = []
    for key, mode in JOBS:
        tasks += [(key, mode, "bo", s) for s in range(args.seeds)]
        tasks += [(key, mode, "random", s) for s in range(args.random_seeds)]
        tasks.append((key, mode, "patent_order", 0))
    rows, t0 = [], time.time()
    with ProcessPoolExecutor(args.workers, initializer=_init) as ex:
        futs = [ex.submit(_run, *t) for t in tasks]
        for i, f in enumerate(as_completed(futs), 1):
            rows += f.result()
            if i % 50 == 0 or i == len(futs):
                print(f"{i}/{len(futs)} done ({time.time() - t0:.0f}s)", flush=True)
    traces = pd.DataFrame(rows)
    out = RESULTS / "replay"
    out.mkdir(parents=True, exist_ok=True)
    traces.to_csv(out / "traces.csv", index=False)

    summaries = []
    for (key, mode, strategy, seed), g in traces.groupby(["campaign", "mode", "strategy", "seed"]):
        g = g.sort_values("step")
        r = ReplayResult(key, strategy, mode, seed, g["picked_index"].tolist(), g["value"].tolist())
        s = summarize_replays([r], get_campaign(key))
        s["campaign"] = key
        summaries.append(s)
    summary = pd.concat(summaries, ignore_index=True)
    summary.to_csv(out / "summary.csv", index=False)
    print(summary.groupby(["campaign", "mode", "strategy"])["experiments_to_target"]
          .agg(["median", "mean", "count"]).round(2).to_string())


if __name__ == "__main__":
    main()
