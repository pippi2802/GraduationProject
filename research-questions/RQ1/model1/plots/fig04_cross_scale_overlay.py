#!/usr/bin/env python3
"""
Figure 4 — CROSS-SCALE overlay (the key RQ1 discriminator).

The same percentile-vs-U curves for tight (10 ms) and soft (100 ms) on ONE axis:
colour = percentile, line style = scale (solid = tight, dashed = soft). If the
tail is dominated by the EXECUTION layer it scales with U similarly at both
timescales; if it is dominated by the DELAY layer (service delay Delta = 2(P-Q),
hypervisor steal) the two scales separate. That separation is the execution-vs-
delay-layer discriminator this figure exists to show.

Regenerate:  python plots/fig04_cross_scale_overlay.py [--timeblock LABEL]
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
    if not C.require_cells(cells, "fig04"):
        return 1

    styles = {"tight": "-", "soft": "--"}
    pcol = {q: c for q, c in zip(C.PCTLS, ["#4C72B0", "#DD8452", "#C44E52"])}
    fig, ax = C.plt.subplots(figsize=(7.5, 5))
    for scale in C.SCALE_ORDER:
        keys = C.sorted_cell_keys(cells, scale)
        us = [k[1] for k in keys]
        for q in C.PCTLS:
            ys = [C.pct(C.load_jobs(cells[k], cfg)["R_us"], q) for k in keys]
            ax.plot(us, ys, styles[scale], marker="o", color=pcol[q],
                    label=f"p{q:g} · {scale}")
    ax.set_yscale("log")
    ax.set_xlabel("utilization U")
    ax.set_ylabel("response time R (us)")
    ax.set_title(f"Model 1 — cross-scale R percentiles (solid=tight, dashed=soft)   [{args.timeblock}]")
    ax.legend(fontsize=8, ncol=2)
    C.save(fig, C.figures_dir(args.timeblock, cfg), "fig04_cross_scale_overlay")
    return 0


if __name__ == "__main__":
    sys.exit(main())
