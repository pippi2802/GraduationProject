#!/usr/bin/env python3
"""
Compute effective bandwidth alpha_eff, service delay Delta_eff, and the
empirical Supply-Bound Function (SBF) from the sampler's server.csv (the RT
container cgroup cpu.stat cumulative usage_usec on a CLOCK_MONOTONIC_RAW clock).

CBS theory (outer level): a server (Q,P) provides bandwidth alpha = Q/P and
bounded service delay Delta = 2*(P - Q); its supply lower bound is
  sbf(t) = max(0, alpha * (t - Delta)).
This tool measures the EMPIRICAL counterparts so you can compare against theory.

  alpha_eff   = total service / wall elapsed over the run (fraction of one core)
  SBF_emp(w)  = min over all start points of [usage(start+w) - usage(start)]
                (worst-case service delivered in any window of length w)
  Delta_eff   = max_w [ w - SBF_emp(w)/alpha_eff ]  (largest horizontal deficit
                between the ideal alpha_eff*t line and the empirical supply)

Stdlib only. Reads usage in microseconds and a raw-ns timeline.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import sys
from pathlib import Path


def load_usage(path: str, target: str):
    ts_us, usage_us = [], []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("target") != target:
                continue
            try:
                t = int(row["ts_raw_ns"]) / 1000.0   # ns -> us
                u = float(row["usage_usec"])
            except (KeyError, ValueError):
                continue
            ts_us.append(t)
            usage_us.append(u)
    # sort by time and make usage monotonic (cumulative counters may hiccup)
    pairs = sorted(zip(ts_us, usage_us))
    ts = [p[0] for p in pairs]
    us = []
    last = None
    for _, u in pairs:
        if last is not None and u < last:
            u = last
        us.append(u)
        last = u
    return ts, us


def usage_at(ts, us, t):
    """Interpolated cumulative usage at absolute time t (us)."""
    i = bisect.bisect_left(ts, t)
    if i <= 0:
        return us[0]
    if i >= len(ts):
        return us[-1]
    t0, t1 = ts[i - 1], ts[i]
    u0, u1 = us[i - 1], us[i]
    if t1 == t0:
        return u1
    return u0 + (u1 - u0) * (t - t0) / (t1 - t0)


def empirical_sbf(ts, us, window_us: float, n_starts: int = 2000) -> float:
    """min over start points of usage(start+window) - usage(start)."""
    t_start, t_end = ts[0], ts[-1]
    if window_us >= (t_end - t_start):
        return float("nan")
    step = (t_end - t_start - window_us) / n_starts
    if step <= 0:
        return float("nan")
    mn = float("inf")
    t = t_start
    while t + window_us <= t_end:
        s = usage_at(ts, us, t + window_us) - usage_at(ts, us, t)
        if s < mn:
            mn = s
        t += step
    return mn if mn != float("inf") else float("nan")


def compute(ts, us, period_us: float):
    span = ts[-1] - ts[0]
    total = us[-1] - us[0]
    alpha_eff = total / span if span > 0 else float("nan")

    # SBF over a grid of window sizes (multiples of the period)
    mults = [0.5, 1, 2, 3, 5, 10, 20, 50, 100]
    sbf = []
    for m in mults:
        w = m * period_us
        if w >= span:
            break
        s = empirical_sbf(ts, us, w)
        sbf.append([w, s])

    # Delta_eff = max horizontal deficit between alpha_eff*t and SBF_emp(t)
    delta_eff = 0.0
    if alpha_eff and alpha_eff == alpha_eff and alpha_eff > 0:
        for w, s in sbf:
            if s != s:
                continue
            deficit = w - (s / alpha_eff)
            if deficit > delta_eff:
                delta_eff = deficit
    return {
        "alpha_eff": alpha_eff,
        "delta_eff_us": delta_eff,
        "span_us": span,
        "total_service_us": total,
        "sbf_emp": sbf,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="alpha_eff / Delta_eff / SBF from server.csv")
    ap.add_argument("server_csv")
    ap.add_argument("--target", default="rt")
    ap.add_argument("--period-us", type=float, required=True)
    ap.add_argument("--out", default=None, help="optional JSON output path")
    args = ap.parse_args()

    ts, us = load_usage(args.server_csv, args.target)
    if len(ts) < 3:
        sys.stderr.write("ERROR: not enough usage samples\n")
        return 2
    res = compute(ts, us, args.period_us)
    text = json.dumps(res, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
