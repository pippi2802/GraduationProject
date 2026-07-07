#!/usr/bin/env python3
"""
Figure 6 — Deadline-miss rate and tardiness vs U.

Left panel : per-cell deadline-miss RATE vs U (both scales), log y-axis. Where a
cell observed ZERO misses the point cannot be drawn on a log axis, so the
rule-of-three upper bound (3/N) is plotted as a hollow marker instead — the
statistically honest "we saw none, but the rate is at most this" ceiling.
Right panel: tardiness distribution summary (p99 and max of tardiness_us) vs U.

Regenerate:  python plots/fig06_deadline_miss.py [--timeblock LABEL]
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
    if not C.require_cells(cells, "fig06"):
        return 1

    fig, (ax_m, ax_t) = C.plt.subplots(1, 2, figsize=(11, 4.4))
    markers = {"tight": "o", "soft": "s"}
    for scale in C.SCALE_ORDER:
        keys = C.sorted_cell_keys(cells, scale)
        us, rate, ro3_u, ro3_y, tp99, tmax = [], [], [], [], [], []
        for (s, u) in keys:
            jobs = C.load_jobs(cells[(s, u)], cfg)
            miss = jobs["miss"]
            n = miss.size
            k = int(np.nansum(miss))
            us.append(u)
            if n > 0 and k > 0:
                rate.append(k / n)
            else:
                rate.append(np.nan)
                if n > 0:
                    ro3_u.append(u); ro3_y.append(C.rule_of_three_upper(n))
            tp99.append(C.pct(jobs["tardiness_us"], 99))
            tmax.append(C.pct(jobs["tardiness_us"], 100))
        ax_m.plot(us, rate, markers[scale] + "-", label=f"miss rate · {scale}")
        if ro3_u:
            ax_m.scatter(ro3_u, ro3_y, marker=markers[scale], facecolors="none",
                         edgecolors="0.4", label=f"3/N bound (0 miss) · {scale}")
        ax_t.plot(us, tp99, markers[scale] + "-", label=f"p99 tardiness · {scale}")
        ax_t.plot(us, tmax, markers[scale] + "--", label=f"max tardiness · {scale}")
    ax_m.set_yscale("log")
    ax_m.set_xlabel("utilization U"); ax_m.set_ylabel("deadline-miss rate")
    ax_m.set_title("miss rate (log y; 3/N where 0 misses)")
    ax_m.legend(fontsize=8)
    ax_t.set_xlabel("utilization U"); ax_t.set_ylabel("tardiness (us)")
    ax_t.set_title("tardiness summary")
    ax_t.legend(fontsize=8)
    fig.suptitle(f"Model 1 — deadline misses & tardiness   [{args.timeblock}]")
    C.save(fig, C.figures_dir(args.timeblock, cfg), "fig06_deadline_miss")
    return 0


if __name__ == "__main__":
    sys.exit(main())
