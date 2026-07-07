#!/usr/bin/env python3
"""
Figure 9 — EVT tail diagnostics for the tight high-U cells.

Two classic extreme-value diagnostics for the R tail of the tight U in {0.9,0.95}
cells (where the tail is the story):
  Left  : mean-excess plot  e(u) = mean(R - u | R > u) vs threshold u. A flat/decreasing
          slope suggests a light (bounded) tail; a persistently rising slope suggests
          a heavy tail with no stable bound.
  Right : return-level plot  R vs return period T = 1/(1 - F(R)) on a log-T axis.
          A curve that keeps climbing without flattening indicates no stable bound.

Regenerate:  python plots/fig09_evt_diag.py [--timeblock LABEL]
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

import common as C


def mean_excess(r, n_thr=60):
    r = np.sort(r[~np.isnan(r)])
    if r.size < 50:
        return np.array([]), np.array([])
    thr = np.quantile(r, np.linspace(0.5, 0.999, n_thr))
    e = []
    for u in thr:
        ex = r[r > u] - u
        e.append(ex.mean() if ex.size else np.nan)
    return thr, np.asarray(e)


def return_levels(r):
    r = np.sort(r[~np.isnan(r)])
    n = r.size
    if n == 0:
        return np.array([]), np.array([])
    F = np.arange(1, n + 1) / (n + 1)
    T = 1.0 / (1.0 - F)
    return T, r


def main() -> int:
    ap = C.add_timeblock_arg(argparse.ArgumentParser(description=__doc__))
    args = ap.parse_args()
    cfg = C.load_config()
    C.set_style()
    cells = C.discover_cells(args.timeblock, cfg)
    if not C.require_cells(cells, "fig09"):
        return 1

    targets = [("tight", u) for u in (0.9, 0.95) if ("tight", u) in cells]
    if not targets:
        targets = C.sorted_cell_keys(cells, "tight")[-2:]
    if not targets:
        sys.stderr.write("[fig09] no tight cells found\n")
        return 1

    fig, (ax_me, ax_rl) = C.plt.subplots(1, 2, figsize=(11, 4.4))
    colors = C.u_colors([k[1] for k in targets])
    for (s, u) in targets:
        r = C.load_jobs(cells[(s, u)], cfg)["R_us"]
        thr, e = mean_excess(r)
        if thr.size:
            ax_me.plot(thr, e, "-o", ms=3, color=colors[u], label=f"U={u:g}")
        T, rl = return_levels(r)
        if T.size:
            ax_rl.plot(T, rl, "-", color=colors[u], label=f"U={u:g}")
    ax_me.set_xlabel("threshold u (us)")
    ax_me.set_ylabel("mean excess e(u) (us)")
    ax_me.set_title("mean-excess (tight high-U)")
    ax_me.legend(fontsize=8)
    ax_rl.set_xscale("log")
    ax_rl.set_xlabel("return period T = 1/(1-F)")
    ax_rl.set_ylabel("response time R (us)")
    ax_rl.set_title("return level")
    ax_rl.legend(fontsize=8)
    fig.suptitle(f"Model 1 — EVT tail diagnostics   [{args.timeblock}]")
    C.save(fig, C.figures_dir(args.timeblock, cfg), "fig09_evt_diag")
    return 0


if __name__ == "__main__":
    sys.exit(main())
