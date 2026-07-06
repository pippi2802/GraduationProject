#!/usr/bin/env python3
"""Attribute deadline misses to virtualization mechanisms (RQ1).

For every per-job record it decides *why* a missed job was late, using the
signals added to the workload:

    host    = steal_us                     -> vCPU steal (mechanism A)
    throttle= throttled_us                 -> CFS cpu.max throttling
    demand  = max(0, exec_time_us - target_c_us)  -> bare-metal C too small (B)
    unexplained = none of the above above a floor -> timekeeping / sched-latency

It prints, per model/mode group:
  * miss ratio,
  * the cause breakdown over missed jobs,
  * conditional medians (steal_us | miss  vs  | no-miss, etc.),
  * point-biserial correlation of deadline_miss with each covariate.

Usage:
    python3 analysis/attribute.py results/m1-ideal
    python3 analysis/attribute.py results/m5-usweep --by util --out attr.csv
    python3 analysis/attribute.py results            # all models at once
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

import parse  # sibling module: load() + split()

# Ignore contributions below this many microseconds when picking the cause.
FLOOR_US = 50


def classify(jobs: pd.DataFrame) -> pd.DataFrame:
    j = jobs.copy()
    for col in ("steal_us", "throttled_us", "exec_time_us", "target_c_us"):
        j[col] = pd.to_numeric(j.get(col), errors="coerce").fillna(0)
    j["demand_us"] = (j["exec_time_us"] - j["target_c_us"]).clip(lower=0)

    contrib = pd.DataFrame({
        "host_steal": j["steal_us"],
        "cfs_throttle": j["throttled_us"],
        "demand_inflation": j["demand_us"],
    })
    top = contrib.max(axis=1)
    cause = contrib.idxmax(axis=1)
    cause = cause.where(top >= FLOOR_US, other="unexplained")
    j["cause"] = cause
    return j


def _corr(binary: pd.Series, x: pd.Series) -> float:
    x = pd.to_numeric(x, errors="coerce")
    b = binary.astype(float)
    if x.nunique(dropna=True) < 2 or b.nunique() < 2:
        return float("nan")
    return float(np.corrcoef(b.fillna(0), x.fillna(0))[0, 1])


def report(jobs: pd.DataFrame, label: str) -> dict:
    n = len(jobs)
    miss = jobs["deadline_miss"].fillna(False).astype(bool)
    miss_ratio = miss.mean() if n else float("nan")

    print(f"\n=== {label}  (n={n}, miss_ratio={miss_ratio:.4f}) ===")

    missed = jobs[miss]
    if len(missed):
        breakdown = missed["cause"].value_counts(normalize=True)
        print("  cause of misses:")
        for cause, frac in breakdown.items():
            print(f"    {cause:<18} {frac:6.1%}  ({int(frac*len(missed))})")
    else:
        print("  cause of misses:  (no misses)")

    print("  conditional medians (miss vs no-miss):")
    for col in ("steal_us", "throttled_us", "preempt_us", "wait_us",
                "exec_time_us", "tardiness_us"):
        if col not in jobs:
            continue
        v = pd.to_numeric(jobs[col], errors="coerce")
        m1 = v[miss].median()
        m0 = v[~miss].median()
        print(f"    {col:<16} miss={m1:>10.1f}   nomiss={m0:>10.1f}")

    print("  point-biserial corr(miss, x):")
    corrs = {c: _corr(miss, jobs[c]) for c in
             ("steal_us", "throttled_us", "preempt_us", "wait_us", "exec_time_us")
             if c in jobs}
    for c, r in sorted(corrs.items(), key=lambda kv: -abs(kv[1]) if kv[1] == kv[1] else 0):
        print(f"    {c:<16} r={r:+.3f}")

    row = {"label": label, "n": n, "miss_ratio": miss_ratio}
    row.update({f"corr_{c}": r for c, r in corrs.items()})
    if len(missed):
        row.update({f"cause_{k}": v for k, v in
                    missed["cause"].value_counts(normalize=True).items()})
    return row


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="results dir or a single .jsonl")
    ap.add_argument("--by", default="mode",
                    help="group column: mode | util | taskset_id | none (default: mode)")
    ap.add_argument("--out", default=None, help="optional CSV of the summary rows")
    args = ap.parse_args(argv)

    jobs, _ = parse.split(parse.load(args.path))
    if jobs.empty:
        print("no per-job records found", file=sys.stderr)
        return 1
    jobs = classify(jobs)

    rows = []
    if args.by == "none" or args.by not in jobs.columns:
        rows.append(report(jobs, args.path))
    else:
        for key, grp in jobs.groupby(args.by):
            rows.append(report(grp, f"{args.by}={key}"))

    if args.out:
        pd.DataFrame(rows).to_csv(args.out, index=False)
        print(f"\nwrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
