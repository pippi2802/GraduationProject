#!/usr/bin/env python3
"""
Figure 8 — Time-series coincidence for a representative high-U cell.

For a representative high-utilization cell (default: tight U=0.95), R per job is
plotted against elapsed wall time on the left axis, with per-window steal and IRQ
deltas on a right axis, so host events line up visually with R spikes. Sampler
"freeze" gap flags are marked. If a canary R stream is available for the same
time-block it is overlaid (thin grey) for corroboration.

Regenerate:  python plots/fig08_timeseries.py [--timeblock LABEL] [--scale tight --u 0.95]
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

import common as C


def _pick_cell(cells, scale, u):
    if (scale, u) in cells:
        return (scale, u)
    keys = C.sorted_cell_keys(cells, scale)
    if keys:
        return keys[-1]                 # highest U of that scale
    return next(iter(cells)) if cells else None


def main() -> int:
    ap = C.add_timeblock_arg(argparse.ArgumentParser(description=__doc__))
    ap.add_argument("--scale", default="tight")
    ap.add_argument("--u", type=float, default=0.95)
    ap.add_argument("--window-s", type=float, default=1.0)
    args = ap.parse_args()
    cfg = C.load_config()
    C.set_style()
    cells = C.discover_cells(args.timeblock, cfg)
    if not C.require_cells(cells, "fig08"):
        return 1

    key = _pick_cell(cells, args.scale, args.u)
    if key is None:
        return 1
    dirs = cells[key]
    d0 = dirs[0]                          # a single run (representative)
    jobs = C.load_jobs([d0], cfg)
    cov = C.load_covariates([d0], cfg)
    canary = C.load_covariates([d0], cfg, target="canary")

    fig, ax = C.plt.subplots(figsize=(11, 4.6))
    t_s = jobs["release_us"] / 1e6
    ax.plot(t_s, jobs["R_us"], lw=0.8, color="#4C72B0", label="R (job)")
    # freeze gap flags
    if cov["gap"].size:
        gaps = cov["elapsed_us"][cov["gap"] > 0] / 1e6
        for g in gaps[:200]:
            ax.axvline(g, color="red", alpha=0.25, lw=0.6)
    ax.set_xlabel("elapsed time (s)")
    ax.set_ylabel("response time R (us)", color="#4C72B0")
    ax.set_title(f"Model 1 — time-series coincidence  cell={key[0]} U={key[1]:g}  [{args.timeblock}]")

    ax2 = ax.twinx()
    ax2.grid(False)
    if cov["elapsed_us"].size:
        sc, sd = C.cumulative_rate_per_window(cov["elapsed_us"], cov["steal_j"], args.window_s)
        ic, idv = C.cumulative_rate_per_window(cov["elapsed_us"], cov["irq_cum"], args.window_s)
        ax2.plot(sc, sd, color="#C44E52", lw=1.0, alpha=0.8, label="steal (Δ/win)")
        ax2.plot(ic, idv / max(1, np.nanmax(idv) if idv.size else 1),
                 color="#8172B3", lw=1.0, alpha=0.6, label="IRQ (Δ/win, norm)")
    ax2.set_ylabel("host activity (per window)")

    if canary["elapsed_us"].size:
        cc, cd = C.cumulative_rate_per_window(canary["elapsed_us"], canary["steal_j"], args.window_s)
        ax2.plot(cc, cd, color="0.5", lw=0.8, ls=":", label="canary steal")

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper right")
    C.save(fig, C.figures_dir(args.timeblock, cfg), "fig08_timeseries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
