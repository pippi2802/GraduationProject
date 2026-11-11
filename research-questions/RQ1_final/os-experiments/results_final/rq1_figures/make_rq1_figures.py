#!/usr/bin/env python3
"""RQ1 ablation figures: relative spread and miss-rate increase of every reverted lever against full isolation.

    python3 make_rq1_figures.py

Read-only on the data and on make_results_final.py (whose definitions are repeated here, not imported, because importing it
would rerun it and rewrite its outputs). Writes only next to this script:
  rq1_{singlecore,multicore}_{tight,soft}.{svg,png}   and   rq1_figures_values.csv
Definitions (same as make_results_final.py, warm-up N_DROP = 6 jobs after every restart):
  S   = p99.9(R) / median(R) of the executed jobs of a cell
  M   = 100 * (misses + skipped) / (jobs + skipped)
  rho = S_c / S_FI,   dM = M_c - M_FI (percentage points), same placement, period, U.  SMT is not part of the ablation.
"""
import pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = pathlib.Path(__file__).resolve().parent
RES = HERE.parent
OS_DATA = RES.parent / "analysis" / "data"
BASE_DATA = RES.parent.parent / "kubedeadline-experiments" / "analysis" / "data"
TESTS = RES.parent.parent / "rq1_significance" / "tests.csv"     # permutation tests, Holm-adjusted (one per configuration, placement, metric; pooled over periods and U)

FULL = "full isolation"
# (scenario code, name in the tables, label in the figures); order = row order top to bottom
LEVERS = [("01", "isolcpus removed", "isolcpus reverted"),
          ("02", "nohz_full removed", "nohz_full reverted"),
          ("03", "rcu_nocbs removed", "rcu_nocbs reverted"),
          ("04", "systemd containment removed", "systemd containment reverted"),
          ("05", "IRQ steering removed", "IRQ steering reverted"),
          ("08", "frequency pinning removed", "frequency pinning reverted"),
          ("06", "boot-params bundle removed", "boot-params bundle reverted")]
PLACEMENTS = [("single-core", "singlecore", "Single-core", "model1", "model1"),
              ("multi-core", "multicore", "Multi-core", "model5", "model5-phys")]
SCALES = [("tight", "tight", 10), ("soft", "soft", 100)]
UTILS = [0.1, 0.5, 0.7, 0.94]
UCOL = {0.1: "#9ec5f4", 0.5: "#5598e7", 0.7: "#256abf", 0.94: "#0d366b"}
N_DROP = 6
XLIM_L, XLIM_R = (0.9, 70.0), (-0.5, 6.0)      # widened below if a value falls outside
TICKS_L = [1, 2, 5, 10, 20]
DODGE = {0.1: 0, 0.5: 0, 0.7: 0, 0.94: 0}      # no vertical offset: all dots of a row sit on its line      # vertical offset inside a row so that equal values do not hide each other
AXIS, TEXT, GRID = "#52514e", "#0b0b0b", "#e1e0d9"


def read(path):
    df = pd.read_csv(path, usecols=["job_index", "R_wall_us", "deadline_miss", "skipped_before", "round", "scale", "U"])
    return df.sort_values(["round", "job_index"]).reset_index(drop=True)


def cell_SM(g):
    n, skipped, misses = len(g), int(g.skipped_before.sum()), int(g.deadline_miss.sum())
    r = g.R_wall_us.to_numpy()
    return 100 * (misses + skipped) / (n + skipped), float(np.percentile(r, 99.9) / np.median(r))


def compute():
    rows = []
    for place, _, _, model, base in PLACEMENTS:
        srcs = [(FULL, BASE_DATA / f"{base}.csv")] + [(name, OS_DATA / f"{code}-{model}.csv") for code, name, _ in LEVERS]
        for name, path in srcs:
            df = read(path)
            for (scale, u), g in df.groupby(["scale", "U"]):
                if u in UTILS:
                    M, S = cell_SM(g[g.job_index >= N_DROP])
                    rows.append(dict(placement=place, configuration=name, scale=scale, U=u, S=S, M=M))
    t = pd.DataFrame(rows)
    fi = t[t.configuration == FULL].set_index(["placement", "scale", "U"])
    k = list(zip(t.placement, t.scale, t.U))
    t["rho"] = t.S.to_numpy() / fi.S.loc[k].to_numpy()
    t["dM"] = t.M.to_numpy() - fi.M.loc[k].to_numpy()
    return t


def check_tables(t):
    """compare S and M with table_<placement>.csv at the precision of the tables (3 decimals M, 2 decimals S)"""
    bad = []
    for place, *_ in PLACEMENTS:
        tab = pd.read_csv(RES / f"table_{place}.csv").dropna(subset=["jobs"])
        tab = tab[tab.configuration != "SMT enabled"]
        m = tab.merge(t[t.placement == place], on=["configuration", "scale", "U"], suffixes=("_tab", ""))
        print(f"  {place}: {len(tab)} cells in table, {len(m)} matched")
        for _, r in m.iterrows():
            if f"{r.miss_rate_pct:.3f}" != f"{r.M:.3f}" or f"{r.tail_spread:.2f}" != f"{r.S:.2f}":
                bad.append((place, r.configuration, r.scale, r.U, r.miss_rate_pct, r.M, r.tail_spread, r.S))
        extra = len(t[t.placement == place]) - len(m)
        if extra:
            print(f"  {place}: {extra} computed cells not in table")
    print("  mismatches:", "none" if not bad else "")
    for b in bad:
        print("   ", b)


def fmt_p(p):
    return "<0.001" if p < 0.001 else (f"{p:.3f}" if p < 0.1 else f"{p:.2f}")


def figure(t, place, pslug, ptitle, scale, sslug, P, xl, xr):
    lab = {name: l for _, name, l in LEVERS}
    lab[FULL] = "full isolation"
    names = [FULL] + [n for _, n, _ in LEVERS]
    tests = pd.read_csv(TESTS)
    tests = tests[tests.placement == place].set_index(["configuration", "metric"])
    sub = t[(t.placement == place) & (t.scale == scale)]
    with plt.rc_context({"font.family": "sans-serif", "font.size": 10, "svg.fonttype": "path"}):
        fig, axes = plt.subplots(1, 2, figsize=(8.2, 4.8), sharey=True)
        for ax, col, ref, met in zip(axes, ["S", "dM"], [1, 0], ["S", "M"]):
            if met == "S":
              ax.text(1.02, 1.0, f"Holm p ({met})", transform=ax.transAxes, ha="left", va="bottom", fontsize=9, color=AXIS)
            for i, n in enumerate(names):
                if met == "S" and (n, met) in tests.index:
                    r = tests.loc[(n, met)]
                    ax.text(1.02, i, fmt_p(r.p_holm) + (" *" if r.significant else ""), transform=ax.get_yaxis_transform(), ha="left", va="center",
                            fontsize=9.5, color=TEXT, fontweight="bold" if r.significant else "normal", clip_on=False)
            for i, n in enumerate(names):
                g = sub[sub.configuration == n].sort_values("U").dropna(subset=[col])
                if n == FULL and col == "dM":
                    continue                      # full isolation is the reference of the miss-rate difference
                if g.empty:
                    continue
                v = g[col].to_numpy()
                ax.plot([v.min(), v.max()], [i, i], color="#cfcfcf", lw=1.0, zorder=2)
                for u, x in zip(g.U, v):
                    ax.plot(x, i + DODGE[u], "o", ms=8, mfc=UCOL[u], mec="white", mew=1.5, zorder=3)
                mx = v.max()
                if (col == "S" and mx >= 1.5) or (col == "dM" and mx >= 0.25):
                    ax.annotate(f"{mx:#.3g}" if col == "S" else f"{mx:+.2f}", (mx, i), xytext=(7, 0), textcoords="offset points",
                                va="center", ha="left", color=TEXT, fontsize=9, zorder=4)
            ax.axvline(ref, color="#6b6a66", lw=1.0, ls=(0, (4, 3)), zorder=1)
            ax.grid(axis="x", color=GRID, lw=0.8, zorder=0); ax.set_axisbelow(True)
            for s in ("top", "right", "left"):
                ax.spines[s].set_visible(False)
            ax.spines["bottom"].set_color(AXIS)
            ax.tick_params(colors=AXIS, length=3)
            ax.tick_params(axis="y", length=0)
        axes[0].set_xscale("log"); axes[0].set_xlim(*xl)
        axes[0].set_xticks(TICKS_L); axes[0].set_xticklabels([f"{x:g}" for x in TICKS_L]); axes[0].minorticks_off()
        axes[1].set_xlim(*xr); axes[1].set_xticks(range(0, 7))
        axes[0].set_ylim(len(names) - 0.4, -0.6)
        axes[0].set_yticks(range(len(names))); axes[0].set_yticklabels([lab[n] for n in names], color=TEXT)
        axes[0].set_xlabel("tail spread $S = p_{99.9}\\,/\\,\\mathrm{median}$", color=TEXT)
        axes[1].set_xlabel("miss rate - miss rate of\nfull isolation [pp]", color=TEXT)
        handles = [Line2D([], [], marker="o", ls="", ms=8, mfc=UCOL[u], mec="white", mew=1.5, label=f"U = {u:g}") for u in UTILS]
        fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.925), labelcolor=TEXT, handletextpad=0.1, columnspacing=1.2, fontsize=10)
        fig.suptitle(f"{ptitle}, {sslug} period (P = {P} ms)", x=0.01, ha="left", y=0.985, fontsize=12, fontweight="bold", color=TEXT)
        fig.text(0.01, 0.01, "Left: tail spread of each configuration (full isolation included). Right: values below 0 mean better than full isolation.\nHolm p (tail spread only): one-sided permutation test vs full isolation,\nall cells of the placement; * = p < 0.05.", fontsize=8.5, color=AXIS, ha="left")
        fig.subplots_adjust(left=0.285, right=0.985, top=0.80, bottom=0.27, wspace=0.30)
        for ext, kw in (("svg", {}), ("png", {"dpi": 200})):
            fig.savefig(HERE / f"rq1_{pslug}_{sslug}.{ext}", facecolor="white", **kw)
        plt.close(fig)


def main():
    t = compute()
    pd.set_option("display.width", 200, "display.max_rows", 500)
    print("CHECK 1: S, M, rho, dM per configuration and cell")
    print(t.round({"S": 3, "M": 3, "rho": 3, "dM": 3}).to_string(index=False))
    print("\n  comparison with table_single-core.csv / table_multi-core.csv:")
    check_tables(t)
    t.to_csv(HERE / "rq1_figures_values.csv", index=False)

    d = t[t.configuration != FULL]
    print("\nS range incl. full isolation:", round(t.S.min(), 3), "..", round(t.S.max(), 3))
    print("\nCHECK 2: values on the 'better' side (rho < 1 relative to FI, or dM < 0)")
    for _, r in d[d.rho < 1].iterrows():
        print(f"  rho={r.rho:.3f}  {r.placement} {r.scale} U={r.U} {r.configuration}")
    for _, r in d[d.dM < 0].iterrows():
        print(f"  dM={r.dM:+.3f}  {r.placement} {r.scale} U={r.U} {r.configuration}")

    xl, xr = XLIM_L, XLIM_R
    if t.S.min() < xl[0] or t.S.max() > xl[1]:
        xl = (min(xl[0], t.S.min() * 0.9), max(xl[1], t.S.max() * 1.5))
    if d.dM.min() < xr[0] or d.dM.max() > xr[1]:
        xr = (min(xr[0], np.floor(d.dM.min() * 2) / 2 - 0.25), max(xr[1], np.ceil(d.dM.max() * 2) / 2 + 0.5))
    print(f"\nrange: S {t.S.min():.3f}..{t.S.max():.3f}, dM {d.dM.min():.3f}..{d.dM.max():.3f}; limits used: left {xl}, right {xr}"
          + ("  (WIDENED)" if (xl, xr) != (XLIM_L, XLIM_R) else "  (defaults kept)"))
    for place, pslug, ptitle, *_ in PLACEMENTS:
        for scale, sslug, P in SCALES:
            figure(t, place, pslug, ptitle, scale, sslug, P, xl, xr)
    print("\nCHECK 3: all four figures use one call path with")
    print("  row order:", [l for _, _, l in LEVERS])
    print("  x limits : left", xl, "right", xr)


main()
