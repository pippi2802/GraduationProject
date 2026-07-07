#!/usr/bin/env python3
"""
Figure 3 — Response-time tail vs utilization.

p50 / p99 / p99.9 / max of R as a function of U, one line per percentile,
separate panels for tight (10 ms) and soft (100 ms). Shows how each percentile
of the response time grows (or does not) as the reservation is loaded toward 1.

Regenerate:  python plots/fig03_tail_vs_util.py [--timeblock LABEL]
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

import common as C


def main() -> int:
    ap = C.add_timeblock_arg(argparse.ArgumentParser(description=__doc__))
    args = ap.parse_args()
    cfg = C.load_config()
    C.set_style()
    cells = C.discover_cells(args.timeblock, cfg)
    if not C.require_cells(cells, "fig03"):
        return 1

    fig, axes = C.plt.subplots(1, len(C.SCALE_ORDER), figsize=(11, 4.2), squeeze=False)
    for ax, scale in zip(axes[0], C.SCALE_ORDER):
        keys = C.sorted_cell_keys(cells, scale)
        us = [k[1] for k in keys]
        series = {q: [] for q in C.PCTLS}
        maxs = []
        for (s, u) in keys:
            r = C.load_jobs(cells[(s, u)], cfg)["R_us"]
            for q in C.PCTLS:
                series[q].append(C.pct(r, q))
            rr = r[~np.isnan(r)]
            maxs.append(float(rr.max()) if rr.size else np.nan)
        for q in C.PCTLS:
            ax.plot(us, series[q], "o-", label=f"p{q:g}")
        ax.plot(us, maxs, "s--", color="k", label="max")
        ax.set_yscale("log")
        ax.set_xlabel("utilization U")
        ax.set_ylabel("response time R (us)")
        ax.set_title(C.SCALE_LABEL[scale])
        ax.legend(fontsize=8)
    fig.suptitle(f"Model 1 — R percentiles vs U   [{args.timeblock}]")
    C.save(fig, C.figures_dir(args.timeblock, cfg), "fig03_tail_vs_util")
    return 0


if __name__ == "__main__":
    sys.exit(main())
