#!/usr/bin/env python3
"""
Figure 7 — Covariate attribution: steal / IRQ time vs the R-tail (POSITIVE plot).

For every cell/time-block, jobs and covariate samples share the cell's elapsed
timeline. We bin both into fixed windows and, per window, compute the R-tail
(max response time) and the per-window delta of the steal counter and of the
per-core interrupt counter. Scattering R-tail against each covariate — with a
least-squares trend and Pearson r — is the positive attribution: it shows the
noise floor tracks HOST steal / IRQ activity, not guest-level contention.

Left  : per-window steal (jiffies) vs window R-tail.
Right : per-window IRQ count vs window R-tail.

Regenerate:  python plots/fig07_covariate_scatter.py [--timeblock LABEL] [--window-s S]
"""
from __future__ import annotations

import argparse
import sys

import numpy as np

import common as C


def _pairs(centers_a, vals_a, centers_b, vals_b):
    """Inner-join two per-window series on rounded window center."""
    da = {round(c, 3): v for c, v in zip(centers_a, vals_a)}
    db = {round(c, 3): v for c, v in zip(centers_b, vals_b)}
    xs, ys = [], []
    for k in da.keys() & db.keys():
        xs.append(db[k]); ys.append(da[k])
    return np.asarray(xs), np.asarray(ys)


def _fit(ax, x, y, color, label):
    ok = ~np.isnan(x) & ~np.isnan(y)
    x, y = x[ok], y[ok]
    if x.size < 3:
        return
    ax.scatter(x, y, s=10, alpha=0.4, color=color)
    b, a = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 50)
    r = np.corrcoef(x, y)[0, 1] if x.size > 1 else np.nan
    ax.plot(xs, b * xs + a, color="k", lw=1.5,
            label=f"{label}: slope={b:.2g}, r={r:.2f}, n={x.size}")


def main() -> int:
    ap = C.add_timeblock_arg(argparse.ArgumentParser(description=__doc__))
    ap.add_argument("--window-s", type=float, default=1.0)
    args = ap.parse_args()
    cfg = C.load_config()
    C.set_style()
    cells = C.discover_cells(args.timeblock, cfg)
    if not C.require_cells(cells, "fig07"):
        return 1

    steal_x, steal_y, irq_x, irq_y = [], [], [], []
    for (s, u), dirs in cells.items():
        for d in dirs:            # one block at a time (shared elapsed origin)
            jobs = C.load_jobs([d], cfg)
            cov = C.load_covariates([d], cfg)
            if jobs["R_us"].size == 0 or cov["elapsed_us"].size == 0:
                continue
            rc, rtail = C.window_reduce(jobs["release_us"], jobs["R_us"],
                                        args.window_s, np.max)
            sc, sdelta = C.cumulative_rate_per_window(cov["elapsed_us"],
                                                      cov["steal_j"], args.window_s)
            ic, idelta = C.cumulative_rate_per_window(cov["elapsed_us"],
                                                      cov["irq_cum"], args.window_s)
            x1, y1 = _pairs(rc, rtail, sc, sdelta)
            x2, y2 = _pairs(rc, rtail, ic, idelta)
            steal_x += list(x1); steal_y += list(y1)
            irq_x += list(x2); irq_y += list(y2)

    fig, (ax_s, ax_i) = C.plt.subplots(1, 2, figsize=(11, 4.4))
    if steal_x:
        _fit(ax_s, np.asarray(steal_x), np.asarray(steal_y), "#4C72B0", "steal")
    else:
        ax_s.text(0.5, 0.5, "no covariate data", transform=ax_s.transAxes,
                  ha="center", va="center", color="0.4")
    ax_s.set_xlabel(f"per-window steal (jiffies / {args.window_s:g}s)")
    ax_s.set_ylabel("window R-tail max (us)")
    ax_s.set_title("steal vs R-tail")
    ax_s.legend(fontsize=8)
    if irq_x:
        _fit(ax_i, np.asarray(irq_x), np.asarray(irq_y), "#DD8452", "IRQ")
    else:
        ax_i.text(0.5, 0.5, "no covariate data", transform=ax_i.transAxes,
                  ha="center", va="center", color="0.4")
    ax_i.set_xlabel(f"per-window interrupts (count / {args.window_s:g}s)")
    ax_i.set_ylabel("window R-tail max (us)")
    ax_i.set_title("IRQ vs R-tail")
    ax_i.legend(fontsize=8)
    fig.suptitle(f"Model 1 — covariate attribution   [{args.timeblock}]")
    C.save(fig, C.figures_dir(args.timeblock, cfg), "fig07_covariate_scatter")
    return 0


if __name__ == "__main__":
    sys.exit(main())
