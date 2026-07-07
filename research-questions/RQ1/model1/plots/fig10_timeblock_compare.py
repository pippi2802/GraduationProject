#!/usr/bin/env python3
"""
Figure 10 — Per-time-block p99.9 comparison.

The tail is driven by hypervisor steal, which is time-correlated, so the SAME
cell can have a different p99.9 depending on when it ran. This figure plots the
p99.9 of R for every cell, one line per time-block, so temporal / tenant-
contention variability is visible. (Always uses ALL discovered time-blocks,
regardless of --timeblock; that spread is the whole point.)

Regenerate:  python plots/fig10_timeblock_compare.py
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

import common as C


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=None)
    ap.parse_args()
    cfg = C.load_config()
    C.set_style()

    blocks = C.list_timeblocks(cfg)
    if not blocks:
        sys.stderr.write("[fig10] no time-blocks under results/. Run at least one.\n")
        return 1

    # ordered cell axis: tight ascending U, then soft ascending U
    all_cells = C.discover_cells("aggregate", cfg)
    order = (C.sorted_cell_keys(all_cells, "tight") +
             C.sorted_cell_keys(all_cells, "soft"))
    if not order:
        sys.stderr.write("[fig10] no cells found.\n")
        return 1
    labels = [f"{s[0]}\nU{u:g}" for (s, u) in order]
    x = np.arange(len(order))

    fig, ax = C.plt.subplots(figsize=(max(8, len(order) * 0.7), 4.6))
    for tb in blocks:
        cells = C.discover_cells(tb, cfg)
        ys = []
        for k in order:
            if k in cells:
                ys.append(C.pct(C.load_jobs(cells[k], cfg)["R_us"], 99.9))
            else:
                ys.append(np.nan)
        ax.plot(x, ys, "o-", ms=4, label=tb)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
    ax.set_yscale("log")
    ax.set_ylabel("p99.9 of response time R (us)")
    ax.set_xlabel("cell")
    ax.set_title("Model 1 — p99.9 per cell across time-blocks")
    ax.legend(fontsize=8, title="time-block")
    C.save(fig, C.figures_dir("aggregate", cfg), "fig10_timeblock_compare")
    return 0


if __name__ == "__main__":
    sys.exit(main())
