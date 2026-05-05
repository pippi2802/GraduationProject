#!/usr/bin/env python3
"""Compute P50/P95/P99 of execution time and plot CDFs for the two conditions.

Usage:
    python analyze.py <results_dir> solo/noisy/all

Expects:
    <results_dir>/solo/rt_periodic.csv
    <results_dir>/noisy/rt_periodic.csv
    <results_dir>/{solo,noisy}/proc_stat.csv  (optional, used for steal-time summary)

Outputs (in <results_dir>):
    summary.txt    -- percentile table + steal-time deltas
    cdf.png        -- CDF of per-invocation execution time
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# --- Execution-time metric ----------------------------------------------------
# We use exec_cpu_us (CPU time spent inside the busy loop) as the workload's
# "execution time per invocation". Under interference this grows because the
# task is preempted/deferred more often, while the wall-clock budget keeps
# moving forward.
#
# response_us (wall-clock from release to finish) is also reported for context.
METRIC = "exec_cpu_us"
PERCENTILES = (50, 95, 99)


def load(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # drop a small warmup window
    return df.iloc[50:].reset_index(drop=True)


def percentiles(series: pd.Series) -> dict[int, float]:
    return {p: float(np.percentile(series, p)) for p in PERCENTILES}


def steal_delta(proc_stat_csv: Path) -> float | None:
    """Return total steal-time ticks accumulated on the aggregate `cpu` line
    between the first and last sample. None if file missing/empty."""
    if not proc_stat_csv.exists():
        return None
    rows = []
    for line in proc_stat_csv.read_text().splitlines():
        if not line or line.startswith("ts_ns"):
            continue
        ts, _, rest = line.partition(",")
        parts = rest.split()
        if not parts or parts[0] != "cpu":
            continue
        # /proc/stat cpu line: cpu user nice system idle iowait irq softirq steal guest guest_nice
        if len(parts) < 9:
            continue
        rows.append((int(ts), int(parts[8])))
    if len(rows) < 2:
        return None
    return float(rows[-1][1] - rows[0][1])


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    condition_choice = sys.argv[2]

    conditions = ["solo", "noisy"]
    data: dict[str, pd.DataFrame] = {}
    for c in conditions:
        if(condition_choice !="all" and c != condition_choice):
            continue
        path = root / c / "rt_periodic.csv"
        if not path.exists():
            print(f"missing: {path}", file=sys.stderr)
            return 1
        data[c] = load(path)

    # --- Summary ------------------------------------------------------------
    lines: list[str] = []
    lines.append(f"Metric: {METRIC} (per-invocation, microseconds)")
    lines.append(f"{'condition':<10} {'n':>6} {'p50':>10} {'p95':>10} {'p99':>10} {'max':>10}")
    for c in conditions:
        if(condition_choice !="all" and c != condition_choice):
            continue
        s = data[c][METRIC]
        p = percentiles(s)
        lines.append(f"{c:<10} {len(s):>6} {p[50]:>10.2f} {p[95]:>10.2f} {p[99]:>10.2f} {s.max():>10.2f}")

    lines.append("")
    lines.append("Steal-time accumulated during run (USER_HZ ticks, aggregate cpu line):")
    for c in conditions:
        if(condition_choice !="all" and c != condition_choice):
            continue
        d = steal_delta(root / c / "proc_stat.csv")
        lines.append(f"  {c:<6} : {'n/a' if d is None else f'{d:.0f}'}")

    summary = "\n".join(lines)
    print(summary)
    (root / "summary.txt").write_text(summary + "\n")

    # --- CDF plot -----------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for c in conditions:
        if(condition_choice !="all" and c != condition_choice):
            continue
        s = np.sort(data[c][METRIC].to_numpy())
        y = np.arange(1, len(s) + 1) / len(s)
        ax.plot(s, y, label=c, linewidth=1.5)
    ax.set_xlabel(f"{METRIC} (us)")
    ax.set_ylabel("CDF")
    ax.set_title("Per-invocation execution time on vanilla AKS")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    out_png = root / "cdf.png"
    fig.savefig(out_png, dpi=140)
    print(f"\nWrote {root / 'summary.txt'}\nWrote {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
