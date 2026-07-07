#!/usr/bin/env python3
"""
Figure 2 — Execution-time C vs response-time R decomposition, per U.

For each cell a pair of violins is drawn side by side: the ACTUAL computation
time C (what the task ran) and the response time R (release -> finish). Since
R = C + delay, the gap between the two violins is the service delay injected by
the CBS supply + hypervisor. One panel per scale.

Regenerate:  python plots/fig02_C_vs_R_violin.py [--timeblock LABEL]
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

import common as C


def _clean(a):
    a = np.asarray(a, dtype=float)
    return a[~np.isnan(a)]


def main() -> int:
    ap = C.add_timeblock_arg(argparse.ArgumentParser(description=__doc__))
    args = ap.parse_args()
    cfg = C.load_config()
    C.set_style()
    cells = C.discover_cells(args.timeblock, cfg)
    if not C.require_cells(cells, "fig02"):
        return 1

    fig, axes = C.plt.subplots(1, len(C.SCALE_ORDER), figsize=(11, 4.2), squeeze=False)
    for ax, scale in zip(axes[0], C.SCALE_ORDER):
        keys = C.sorted_cell_keys(cells, scale)
        positions_c, positions_r, data_c, data_r, ticks, labels = [], [], [], [], [], []
        for i, (s, u) in enumerate(keys):
            jobs = C.load_jobs(cells[(s, u)], cfg)
            c, r = _clean(jobs["C_us"]), _clean(jobs["R_us"])
            base = i * 1.0
            if c.size:
                positions_c.append(base - 0.16); data_c.append(c)
            if r.size:
                positions_r.append(base + 0.16); data_r.append(r)
            ticks.append(base); labels.append(f"{u:g}")
        if data_c:
            vp = ax.violinplot(data_c, positions=positions_c, widths=0.3,
                               showmeans=False, showextrema=False)
            for b in vp["bodies"]:
                b.set_facecolor("#4C72B0"); b.set_alpha(0.7)
        if data_r:
            vp = ax.violinplot(data_r, positions=positions_r, widths=0.3,
                               showmeans=False, showextrema=False)
            for b in vp["bodies"]:
                b.set_facecolor("#DD8452"); b.set_alpha(0.7)
        ax.set_xticks(ticks); ax.set_xticklabels(labels)
        ax.set_xlabel("utilization U")
        ax.set_ylabel("time (us)")
        ax.set_title(C.SCALE_LABEL[scale])
        ax.plot([], [], color="#4C72B0", lw=6, alpha=0.7, label="C (execution)")
        ax.plot([], [], color="#DD8452", lw=6, alpha=0.7, label="R (response)")
        ax.legend(fontsize=8)
    fig.suptitle(f"Model 1 — C vs R decomposition (R = C + delay)   [{args.timeblock}]")
    C.save(fig, C.figures_dir(args.timeblock, cfg), "fig02_C_vs_R_violin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
