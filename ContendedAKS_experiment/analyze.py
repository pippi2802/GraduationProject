#!/usr/bin/env python3
"""Per-task statistics for the contended-AKS experiment.

For each task CSV in <results_dir> reports:
  - n invocations (after warmup drop)
  - mean / variance / std / p50 / p95 / p99 / max of exec_cpu_us
  - mean / variance / std / p50 / p95 / p99 / max of response_us
  - deadline miss count and miss rate
  - configured period_us, runtime_us (inferred from CSV)

Also writes:
  summary.txt  -- the textual table
  cdf.png      -- per-task CDF of response_us

Usage:
    python analyze.py <results_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

WARMUP = 20  # drop first N invocations of every task


def load(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if len(df) > WARMUP:
        df = df.iloc[WARMUP:].reset_index(drop=True)
    return df


def task_stats(name: str, df: pd.DataFrame) -> dict:
    exec_us = df["exec_cpu_us"].to_numpy(dtype=float)
    resp_us = df["response_us"].to_numpy(dtype=float)
    miss = df["miss"].to_numpy(dtype=int)
    # period inferred from release_ns deltas (median to be robust)
    rel = df["release_ns"].to_numpy(dtype=np.int64)
    if len(rel) >= 2:
        period_us = float(np.median(np.diff(rel))) / 1000.0
    else:
        period_us = float("nan")
    return {
        "task": name,
        "n": len(df),
        "period_us": period_us,
        "exec_mean": exec_us.mean(),
        "exec_var": exec_us.var(ddof=1) if len(exec_us) > 1 else 0.0,
        "exec_std": exec_us.std(ddof=1) if len(exec_us) > 1 else 0.0,
        "exec_p50": float(np.percentile(exec_us, 50)),
        "exec_p95": float(np.percentile(exec_us, 95)),
        "exec_p99": float(np.percentile(exec_us, 99)),
        "exec_max": exec_us.max(),
        "resp_mean": resp_us.mean(),
        "resp_var": resp_us.var(ddof=1) if len(resp_us) > 1 else 0.0,
        "resp_std": resp_us.std(ddof=1) if len(resp_us) > 1 else 0.0,
        "resp_p50": float(np.percentile(resp_us, 50)),
        "resp_p95": float(np.percentile(resp_us, 95)),
        "resp_p99": float(np.percentile(resp_us, 99)),
        "resp_max": resp_us.max(),
        "miss_count": int(miss.sum()),
        "miss_rate": float(miss.mean()),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    csvs = sorted(root.glob("c?_task*.csv"))
    if not csvs:
        print(f"No task CSVs found in {root}", file=sys.stderr)
        return 1

    rows = []
    series = {}
    for p in csvs:
        df = load(p)
        rows.append(task_stats(p.stem, df))
        series[p.stem] = df["response_us"].to_numpy(dtype=float)

    out = pd.DataFrame(rows)
    pd.set_option("display.float_format", lambda v: f"{v:10.2f}")

    cols_main = ["task", "n", "period_us",
                 "exec_mean", "exec_var", "exec_p95", "exec_p99", "exec_max",
                 "resp_mean", "resp_var", "resp_p95", "resp_p99", "resp_max",
                 "miss_count", "miss_rate"]
    text = out[cols_main].to_string(index=False)
    print(text)
    (root / "summary.txt").write_text(text + "\n")

    # CDF of response time per task
    fig, ax = plt.subplots(figsize=(8, 5))
    for name, s in series.items():
        s = np.sort(s)
        y = np.arange(1, len(s) + 1) / len(s)
        ax.plot(s, y, label=name, linewidth=1.3)
    ax.set_xlabel("response_us (release -> finish)")
    ax.set_ylabel("CDF")
    ax.set_title("Per-task response time on contended vanilla AKS")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_png = root / "cdf.png"
    fig.savefig(out_png, dpi=140)
    print(f"\nWrote {root / 'summary.txt'}\nWrote {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
