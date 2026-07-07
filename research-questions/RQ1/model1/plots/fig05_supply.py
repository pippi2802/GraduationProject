#!/usr/bin/env python3
"""
Figure 5 — Supply level: effective bandwidth and service delay vs U.

Uses the RT container cgroup cpu.stat stream (server.csv) via parse/supply.py to
measure, per cell:
  alpha_eff   — delivered CPU fraction (should track the theoretical alpha = Q/P)
  Delta_eff   — largest service delay (should stay under Delta = 2*(P - Q))
Rows: alpha (top), Delta (bottom). Columns: tight, soft. Theory reference lines
are drawn for both. Cells with no server.csv are skipped (annotated).

Regenerate:  python plots/fig05_supply.py [--timeblock LABEL]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

import common as C

sys.path.insert(0, str(C.ROOT / "parse"))
import supply  # noqa: E402


def _cell_supply(cell_dirs, period_us, cfg):
    """Average alpha_eff / Delta_eff across the given (per-block) cell dirs."""
    alphas, deltas = [], []
    fname = cfg["results"]["server_csv"]
    for d in cell_dirs:
        p = Path(d) / fname
        if not p.exists():
            continue
        ts, us = supply.load_usage(str(p), "rt")
        if len(ts) < 3:
            continue
        res = supply.compute(ts, us, period_us)
        alphas.append(res["alpha_eff"])
        deltas.append(res["delta_eff_us"])
    a = np.nanmean(alphas) if alphas else np.nan
    dl = np.nanmean(deltas) if deltas else np.nan
    return a, dl


def main() -> int:
    ap = C.add_timeblock_arg(argparse.ArgumentParser(description=__doc__))
    args = ap.parse_args()
    cfg = C.load_config()
    C.set_style()
    cells = C.discover_cells(args.timeblock, cfg)
    if not C.require_cells(cells, "fig05"):
        return 1

    fig, axes = C.plt.subplots(2, len(C.SCALE_ORDER), figsize=(11, 7.5), squeeze=False)
    any_supply = False
    for col, scale in enumerate(C.SCALE_ORDER):
        period_us = cfg["scales"][scale]["period_us"]
        keys = C.sorted_cell_keys(cells, scale)
        us, a_eff, d_eff, a_th, d_th = [], [], [], [], []
        for (s, u) in keys:
            period = period_us
            q_us = round(u * period)
            a, dl = _cell_supply(cells[(s, u)], period, cfg)
            us.append(u); a_eff.append(a); d_eff.append(dl)
            a_th.append(q_us / period)                 # alpha = Q/P
            d_th.append(2 * (period - q_us))           # Delta = 2(P - Q)
        if np.any(~np.isnan(a_eff)):
            any_supply = True
        ax_a, ax_d = axes[0][col], axes[1][col]
        ax_a.plot(us, a_th, "k--", label="alpha = Q/P (theory)")
        ax_a.plot(us, a_eff, "o-", color="#4C72B0", label="alpha_eff (measured)")
        ax_a.set_ylabel("bandwidth alpha (fraction of a core)")
        ax_a.set_title(f"supply — {C.SCALE_LABEL[scale]}")
        ax_a.legend(fontsize=8)
        ax_d.plot(us, d_th, "k--", label="Delta = 2(P-Q) (theory)")
        ax_d.plot(us, d_eff, "s-", color="#C44E52", label="Delta_eff (measured)")
        ax_d.set_xlabel("utilization U")
        ax_d.set_ylabel("service delay Delta (us)")
        ax_d.legend(fontsize=8)
    if not any_supply:
        axes[0][0].text(0.5, 0.5, "no server.csv found\n(theory lines only)",
                        transform=axes[0][0].transAxes, ha="center", va="center",
                        fontsize=10, color="0.4")
    fig.suptitle(f"Model 1 — effective supply vs theory   [{args.timeblock}]")
    C.save(fig, C.figures_dir(args.timeblock, cfg), "fig05_supply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
