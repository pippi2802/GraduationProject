#!/usr/bin/env python3
"""Compare RT-DRA vs vanilla: deadline-miss ratio and response times vs U.

Outputs:
  * headline plot  : miss ratio vs utilisation U, one series per mode
  * schedulability : fraction of task sets with zero misses, per mode per U bin
  * response plot  : p99 response-time distribution per mode
  * a summary CSV   : per (mode, taskset) miss ratio + p99 response time

Expectation: with interference on, RT-DRA stays ~0 for CARTS-schedulable sets
while vanilla's miss ratio rises with U / contention.

matplotlib is optional; if missing, tables/CSVs are still produced.
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

# parse.py lives next to this file.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parse import load  # noqa: E402

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except Exception:  # pragma: no cover - plotting is optional
    HAVE_MPL = False


def per_taskset(df: pd.DataFrame) -> pd.DataFrame:
    """Per (mode, taskset_id) miss ratio, p99 response time, overrun count."""
    g = df.groupby(["mode", "taskset_id"])
    out = g.agg(
        util=("util", "first"),
        n_tasks=("n_tasks", "first"),
        jobs=("deadline_miss", "size"),
        miss_ratio=("deadline_miss", "mean"),
        p99_resp_us=("response_time_us", lambda s: s.quantile(0.99)),
        overruns=("overrun", "sum"),
    ).reset_index()
    return out


def schedulability(per_set: pd.DataFrame, bin_width: float = 0.2) -> pd.DataFrame:
    """Fraction of task sets with zero misses, per mode per U bin."""
    ps = per_set.copy()
    ps["u_bin"] = (ps["util"] / bin_width).round().astype(int) * bin_width
    ps["schedulable"] = ps["miss_ratio"] == 0.0
    out = (ps.groupby(["mode", "u_bin"])["schedulable"]
              .mean().reset_index(name="success_rate"))
    return out


def plot_miss_vs_u(per_set: pd.DataFrame, out_path: str, bin_width: float = 0.2):
    if not HAVE_MPL:
        return
    ps = per_set.copy()
    ps["u_bin"] = (ps["util"] / bin_width).round().astype(int) * bin_width
    agg = ps.groupby(["mode", "u_bin"])["miss_ratio"].mean().reset_index()
    plt.figure(figsize=(7, 4.5))
    for mode, sub in agg.groupby("mode"):
        sub = sub.sort_values("u_bin")
        plt.plot(sub["u_bin"], sub["miss_ratio"], marker="o", label=mode)
    plt.xlabel("Utilisation U")
    plt.ylabel("Mean deadline-miss ratio")
    plt.title("Deadline-miss ratio vs utilisation (interference on)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def plot_resp_dist(df: pd.DataFrame, out_path: str):
    if not HAVE_MPL:
        return
    plt.figure(figsize=(7, 4.5))
    for mode, sub in df.groupby("mode"):
        resp_ms = sub["response_time_us"] / 1000.0
        plt.hist(resp_ms, bins=80, histtype="step", density=True, label=mode)
    plt.xlabel("Response time (ms)")
    plt.ylabel("Density")
    plt.title("Response-time distribution by mode")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="RT-DRA vs vanilla comparison")
    p.add_argument("results", help="results directory or combined JSONL")
    p.add_argument("--out-dir", default="analysis_out")
    p.add_argument("--bin-width", type=float, default=0.2)
    args = p.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    df = load(args.results)
    if df.empty:
        print("no records found", file=sys.stderr)
        return 1

    per_set = per_taskset(df)
    per_set.to_csv(os.path.join(args.out_dir, "per_taskset.csv"), index=False)

    sched = schedulability(per_set, args.bin_width)
    sched.to_csv(os.path.join(args.out_dir, "schedulability.csv"), index=False)

    plot_miss_vs_u(per_set, os.path.join(args.out_dir, "miss_ratio_vs_U.png"),
                   args.bin_width)
    plot_resp_dist(df, os.path.join(args.out_dir, "response_dist.png"))

    # Headline table to stdout.
    print("\n=== miss ratio by mode and U bin ===")
    ps = per_set.copy()
    ps["u_bin"] = (ps["util"] / args.bin_width).round().astype(int) * args.bin_width
    table = ps.pivot_table(index="u_bin", columns="mode",
                           values="miss_ratio", aggfunc="mean")
    print(table.to_string(float_format=lambda x: f"{x:.3f}"))

    print("\n=== schedulability success rate (zero-miss task sets) ===")
    stab = sched.pivot_table(index="u_bin", columns="mode",
                             values="success_rate")
    print(stab.to_string(float_format=lambda x: f"{x:.3f}"))

    print(f"\noutputs written to {args.out_dir}/"
          + ("" if HAVE_MPL else "  (matplotlib missing: plots skipped)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
