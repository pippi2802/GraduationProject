#!/usr/bin/env python3
"""Step 1: from the victim runs, the platform factors alpha_platform(m); from the empty-job run, the noise floor. Run it after
run_platform.sh (which calls it), or alone:   python3 compute_platform.py

Reads  results/victim_raw.csv          dial, condition, trial, elapsed_ms   (conditions cache_alone, cache_enemy, memory_alone, memory_enemy)
       results/victim_summary.csv      optional: maps dial -> number of enemy cores (otherwise dial k = k enemy cores)
       results/noise_floor/instance0.csv   optional (P3)
Writes results/platform_factor.csv     m, medians, ratios, alpha_platform   <- read by step 4
       results/noise_floor_summary.csv overhead and dispatch latency       <- read by step 4"""
import os
import numpy as np
import pandas as pd

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


class PlatformFactor:
    """alpha_platform(m) = median run time of the victim with m enemy cores / median run time of the victim alone, the larger of the cache
    and the memory victim. The alone runs of the same dial are the denominator."""

    def __init__(self, raw, summary=None):
        med = raw.groupby(["dial", "condition"]).elapsed_ms.median().unstack("condition")
        n = raw.groupby(["dial", "condition"]).size().unstack("condition").min(axis=1)
        t = pd.DataFrame(index=med.index)
        for v in ("cache", "memory"):
            if {f"{v}_alone", f"{v}_enemy"} <= set(med.columns):
                t[f"{v}_alone_ms"], t[f"{v}_enemy_ms"] = med[f"{v}_alone"], med[f"{v}_enemy"]
                t[f"{v}_ratio"] = med[f"{v}_enemy"] / med[f"{v}_alone"]
        if t.empty:
            raise SystemExit("victim_raw.csv: expected the conditions cache_alone/cache_enemy and/or memory_alone/memory_enemy")
        t["alpha_platform"] = t[[c for c in t if c.endswith("_ratio")]].max(axis=1)
        t["trials"] = n
        m = summary.set_index("dial").n_cores.reindex(t.index) if summary is not None else pd.Series(t.index, index=t.index)    # dial k = k enemy cores
        t.insert(0, "m", m.astype(int).to_numpy())
        self.table = t.set_index("m")


class NoiseFloor:
    """Overhead of the runtime at the chosen period: CPU time of the empty job, and the dispatch latency (start - release)."""

    def __init__(self, df):
        d = df[(df.skipped == 0) & (df.warmup == 0)]
        period_ms = float(np.median(np.diff(df.sort_values("job_id").release_ns))) / 1e6
        us = lambda s: s.to_numpy() / 1e3
        self.table = pd.DataFrame([dict(
            period_ms=period_ms, jobs=len(d), overhead_us_median=np.median(us(d.cpu_ns)), overhead_us_p99=np.quantile(us(d.cpu_ns), .99),
            overhead_us_max=us(d.cpu_ns).max(), dispatch_us_median=np.median(us(d.wait_ns)), dispatch_us_p99=np.quantile(us(d.wait_ns), .99),
            dispatch_us_max=us(d.wait_ns).max(), late=int((d.deadline_met == 0).sum()))])


if __name__ == "__main__":
    raw = pd.read_csv(f"{R}/victim_raw.csv")
    summary = pd.read_csv(f"{R}/victim_summary.csv") if os.path.exists(f"{R}/victim_summary.csv") else None
    pf = PlatformFactor(raw, summary).table
    pf.to_csv(f"{R}/platform_factor.csv")
    print("alpha_platform(m) = median with m enemy cores / median alone (larger of the cache and memory victim):")
    print(pf.round(3).to_string())
    nf = f"{R}/noise_floor/instance0.csv"
    if os.path.exists(nf):
        t = NoiseFloor(pd.read_csv(nf)).table
        t.to_csv(f"{R}/noise_floor_summary.csv", index=False)
        print("\nnoise floor (empty job, microseconds):")
        print(t.round(2).to_string(index=False))
    else:
        print("\nno noise floor run (results/noise_floor/instance0.csv): optional, skipped")
