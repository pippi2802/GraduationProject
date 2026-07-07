#!/usr/bin/env python3
"""
Figure 1 — Response-time ECDF / CCDF per cell.

One panel per scale (tight, soft), all U levels overlaid. The CCDF (survival
function) is drawn on a LOG y-axis so the deep tail (p99.9 and beyond) is legible;
a reference line marks the 1e-3 survival level (= p99.9). This is the primary
"where does the tail go" view.

Regenerate:  python plots/fig01_response_ecdf_ccdf.py [--timeblock LABEL]
"""
from __future__ import annotations

import argparse
import sys

import common as C


def main() -> int:
    ap = C.add_timeblock_arg(argparse.ArgumentParser(description=__doc__))
    args = ap.parse_args()
    cfg = C.load_config()
    C.set_style()
    cells = C.discover_cells(args.timeblock, cfg)
    if not C.require_cells(cells, "fig01"):
        return 1

    fig, axes = C.plt.subplots(1, len(C.SCALE_ORDER), figsize=(11, 4.2), squeeze=False)
    for ax, scale in zip(axes[0], C.SCALE_ORDER):
        keys = C.sorted_cell_keys(cells, scale)
        colors = C.u_colors([k[1] for k in keys])
        for (s, u) in keys:
            jobs = C.load_jobs(cells[(s, u)], cfg)
            x, surv = C.ccdf(jobs["R_us"])
            if x.size == 0:
                continue
            ax.step(x, surv, where="post", color=colors[u], label=f"U={u:g}")
        ax.axhline(1e-3, color="0.5", ls="--", lw=1, label="p99.9 (1e-3)")
        ax.set_yscale("log")
        ax.set_xlabel("response time R (us)")
        ax.set_ylabel("CCDF  P(R > x)")
        ax.set_title(C.SCALE_LABEL[scale])
        ax.legend(fontsize=8, ncol=2)
    fig.suptitle(f"Model 1 — response-time tail (CCDF)   [{args.timeblock}]")
    C.save(fig, C.figures_dir(args.timeblock, cfg), "fig01_response_ccdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
