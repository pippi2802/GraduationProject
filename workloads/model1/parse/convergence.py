#!/usr/bin/env python3
"""
Running-p99.9 convergence checker for the per-cell stopping rule.

Used by run_model1.py to decide when a cell has collected enough jobs.

Rule (from config.yaml stopping_rule):
  * discard the first `warmup_jobs` completed jobs (done upstream by the parser)
  * track the running p99.9 of response time R (plus running max and an EVT
    peaks-over-threshold tail-index estimate, as diagnostics)
  * "converged" = the p99.9 computed over ALL N jobs differs from the p99.9
    computed over the first (1 - window_fraction)*N jobs by < rel_change_threshold
    (i.e. adding the most recent `window_fraction` of jobs barely moves p99.9)
  * only evaluate once N >= max(n_min, min_window_jobs)

Stdlib only (no numpy/scipy). Importable + CLI.
"""
from __future__ import annotations

import math
from typing import Sequence


def percentile(sorted_vals: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile, q in [0,100]. Input MUST be sorted."""
    n = len(sorted_vals)
    if n == 0:
        return float("nan")
    if n == 1:
        return float(sorted_vals[0])
    rank = (q / 100.0) * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = rank - lo
    return float(sorted_vals[lo]) * (1 - frac) + float(sorted_vals[hi]) * frac


def hill_tail_index(values: Sequence[float], threshold_quantile: float = 0.95):
    """EVT peaks-over-threshold tail index via the Hill estimator.

    Returns the Hill estimate of the tail (shape) parameter xi for the upper
    tail. Larger xi => heavier tail. None if too few exceedances.
    """
    n = len(values)
    if n < 100:
        return None
    s = sorted(values)
    k = int((1.0 - threshold_quantile) * n)
    if k < 10:
        return None
    top = s[-k:]                      # k largest
    thr = s[-k - 1]
    if thr <= 0:
        # shift to positive support for the log-based Hill estimator
        shift = 1.0 - thr
        top = [v + shift for v in top]
        thr = thr + shift
    logs = [math.log(v) - math.log(thr) for v in top if v > 0]
    if not logs:
        return None
    return sum(logs) / len(logs)


def check_convergence(
    r_values: Sequence[float],
    n_min: int,
    rel_change_threshold: float,
    window_fraction: float,
    min_window_jobs: int,
) -> dict:
    """Evaluate the stopping metric over the post-warmup response times."""
    n = len(r_values)
    result = {
        "n": n,
        "p99_9": float("nan"),
        "running_max": float("nan"),
        "tail_index": None,
        "rel_change": float("nan"),
        "converged": False,
    }
    if n == 0:
        return result

    s = sorted(r_values)
    result["running_max"] = float(s[-1])
    result["p99_9"] = percentile(s, 99.9)
    result["tail_index"] = hill_tail_index(r_values)

    if n < max(n_min, min_window_jobs):
        return result

    # p99.9 over the first (1 - window_fraction) fraction vs. over all N
    cut = int(round((1.0 - window_fraction) * n))
    if cut < min_window_jobs:
        return result
    s_prev = sorted(r_values[:cut])
    p_prev = percentile(s_prev, 99.9)
    p_now = result["p99_9"]
    if p_prev and not math.isnan(p_prev) and p_prev != 0:
        rel = abs(p_now - p_prev) / abs(p_prev)
        result["rel_change"] = rel
        result["converged"] = rel < rel_change_threshold
    return result


def _load_r_from_csv(path: str) -> list[float]:
    import csv
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                out.append(float(row["R_us"]))
            except (KeyError, ValueError):
                pass
    return out


if __name__ == "__main__":
    import argparse
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import model1lib as m1

    ap = argparse.ArgumentParser(description="Check per-cell convergence from jobs.csv")
    ap.add_argument("jobs_csv")
    ap.add_argument("--n-min", type=int, default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = m1.load_config(args.config)
    conv = cfg["stopping_rule"]["convergence"]
    n_min = args.n_min if args.n_min is not None else cfg["stopping_rule"]["n_min"]
    r = _load_r_from_csv(args.jobs_csv)
    res = check_convergence(
        r,
        n_min=n_min,
        rel_change_threshold=conv["rel_change_threshold"],
        window_fraction=conv["window_fraction"],
        min_window_jobs=conv["min_window_jobs"],
    )
    print(json.dumps(res, indent=2))
