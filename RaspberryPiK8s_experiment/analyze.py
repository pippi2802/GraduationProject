#!/usr/bin/env python3
"""Per-task statistics for the Raspberry-Pi-on-Kubernetes experiment.

Identical methodology to the AKS / bare-metal Pi analyzers; only the plot
title differs. This lets you drop the three results directories next to
each other (AKS / bare-metal Pi / k8s-on-Pi) and compare them directly.

Outputs:
  summary.txt  -- the textual table
  cdf.png      -- per-task CDF of response_us

Usage:
    python3 analyze.py <results_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

WARMUP = 20


def load(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if len(df) > WARMUP:
        df = df.iloc[WARMUP:].reset_index(drop=True)
    return df


def plot_distributions(root: Path, csvs: list, column: str, title: str,
                       out_path: Path) -> Path:
    """One subplot per task: normalized histogram + Gaussian fit (mean/std)
    + vertical lines at p50/p95/p99."""
    n = len(csvs)
    cols = 3 if n >= 3 else n
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 3.2 * rows),
                             squeeze=False)
    for ax, p in zip(axes.flat, csvs):
        df = load(p)
        x = df[column].to_numpy(dtype=float)
        mu = float(np.mean(x))
        sd = float(np.std(x, ddof=1)) if len(x) > 1 else 0.0
        p50 = float(np.percentile(x, 50))
        p95 = float(np.percentile(x, 95))
        p99 = float(np.percentile(x, 99))
        ax.hist(x, bins=60, density=True, alpha=0.55,
                color="#4477aa", edgecolor="none", label="empirical")
        if sd > 0:
            xs = np.linspace(x.min(), x.max(), 400)
            ys = (1.0 / (sd * np.sqrt(2 * np.pi))) * \
                 np.exp(-0.5 * ((xs - mu) / sd) ** 2)
            ax.plot(xs, ys, color="#cc3311", linewidth=1.4,
                    label=f"N({mu:.1f}, {sd:.1f}\u00b2)")
        ymax = ax.get_ylim()[1]
        for v, lbl, ls, c in [
            (p50, "p50", ":",  "#444444"),
            (p95, "p95", "--", "#117733"),
            (p99, "p99", "-.", "#aa3377"),
        ]:
            ax.axvline(v, color=c, linestyle=ls, linewidth=1.0)
            ax.text(v, ymax * 0.95, f" {lbl}={v:.0f}", color=c,
                    fontsize=7, rotation=90, va="top")
        ax.set_title(p.stem, fontsize=10)
        ax.set_xlabel(column + " (us)")
        ax.set_ylabel("density")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, loc="upper right")
    for ax in axes.flat[n:]:
        ax.set_visible(False)
    fig.suptitle(title, fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def task_stats(name: str, df: pd.DataFrame) -> dict:
    exec_us = df["exec_cpu_us"].to_numpy(dtype=float)
    resp_us = df["response_us"].to_numpy(dtype=float)
    miss = df["miss"].to_numpy(dtype=int)
    rel = df["release_ns"].to_numpy(dtype=np.int64)
    period_us = float(np.median(np.diff(rel))) / 1000.0 if len(rel) >= 2 else float("nan")
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
                 "exec_mean", "exec_var", "exec_p50", "exec_p95", "exec_p99", "exec_max",
                 "resp_mean", "resp_var", "resp_p50", "resp_p95", "resp_p99", "resp_max",
                 "miss_count", "miss_rate"]
    text = out[cols_main].to_string(index=False)
    print(text)
    (root / "summary.txt").write_text(text + "\n")

    fig, ax = plt.subplots(figsize=(8, 5))
    for name, s in series.items():
        s = np.sort(s)
        y = np.arange(1, len(s) + 1) / len(s)
        ax.plot(s, y, label=name, linewidth=1.3)
    ax.set_xlabel("response_us (release -> finish)")
    ax.set_ylabel("CDF")
    ax.set_title("Per-task response time on Raspberry Pi worker (k8s, contended)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_png = root / "cdf.png"
    fig.savefig(out_png, dpi=140)

    title = "Raspberry Pi worker, k8s, contended"
    dist_exec = plot_distributions(root, csvs, "exec_cpu_us",
                                   f"Per-task execution-time distribution ({title})",
                                   root / "dist_exec.png")
    dist_resp = plot_distributions(root, csvs, "response_us",
                                   f"Per-task response-time distribution ({title})",
                                   root / "dist_resp.png")
    print(f"\nWrote {root / 'summary.txt'}\nWrote {out_png}\nWrote {dist_exec}\nWrote {dist_resp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
