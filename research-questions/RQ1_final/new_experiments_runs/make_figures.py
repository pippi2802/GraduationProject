#!/usr/bin/env python3
"""Figures of the rerun, same layout and styling as the existing RQ1 figures. Needs output/step1_runs.csv and output/step3_tests.csv.

Cell value (fixed in advance): tail spread S = p99.9/median of the response times of the four rounds pooled; miss+skip rate M = lost releases / releases of
the four rounds pooled (skips detected from gaps in release_us); worst window m = smallest m_k100 over the four rounds; longest run = largest
longest_lost_run over the four rounds.
  rq1_{singlecore,multicore}_{tight,soft}.{svg,png}   left: tail spread (log), right: miss+skip rate in % (log; a rate of 0 is drawn as an open
                                                       marker on the axis labelled 0), one row per configuration with full isolation on top, one dot per U.
                                                       Holm p of the step-3 tests (pooled over the cells) written at the right edge of each panel.
  heatmap_worst_window_{single-core,multi-core}.{svg,png}   m per cell
  heatmap_longest_run_{single-core,multi-core}.{svg,png}    longest run of consecutive lost releases per cell, same grid
n/r (not run) cells are hatched. Values: output/figure_values.csv
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

import common as cm

UCOL = {0.1: "#9ec5f4", 0.5: "#5598e7", 0.7: "#256abf", 0.94: "#0d366b"}
AXIS, TEXT, GRID = "#52514e", "#0b0b0b", "#e1e0d9"
ZERO_X = 0.002
RED_BLACK = LinearSegmentedColormap.from_list("red_to_black", [(0.0, "#ffffff"), (0.04, "#fee0d2"), (0.30, "#fb6a4a"), (0.60, "#cb181d"), (0.85, "#67000d"), (1.0, "#000000")])


def cell_values():
    runs, _ = cm.get_runs()
    t1 = pd.read_csv(cm.OUT / "step1_runs.csv")
    rows = []
    for (pl, c, s, u) in cm.cells():
        rr = [runs[(pl, c, s, u, r)] for r in cm.ROUNDS if (pl, c, s, u, r) in runs]
        if not rr:
            continue
        P = cm.PERIOD[s]
        lost = total = 0
        for a in rr:
            seq, sk = cm.lost_sequence(a, P)
            lost += int(seq.sum())
            total += len(seq)
        R = np.concatenate([a["R_wall_us"] for a in rr])
        g = t1[(t1.placement == pl) & (t1.configuration == c) & (t1.scale == s) & (t1.U == u)]
        rows.append(dict(placement=pl, configuration=c, scale=s, U=u, n_rounds=len(rr), miss_skip_pct=100.0 * lost / total,
                         tail_spread=float(np.percentile(R, 99.9) / np.median(R)), m_worst_round=int(g.m_k100.min()), longest_run_max_round=int(g.longest_lost_run.max())))
    v = pd.DataFrame(rows)
    v.to_csv(cm.OUT / "figure_values.csv", index=False)
    return v


def fmt_p(p):
    return "<0.001" if p < 0.001 else (f"{p:.3f}" if p < 0.1 else f"{p:.2f}")


def figure(v, tests, place, pslug, ptitle, scale, sslug, P, xl_s, xl_m):
    names = cm.CONFIGS
    sub = v[(v.placement == place) & (v.scale == scale)]
    tt = tests[tests.placement == place].set_index(["configuration", "metric"])
    with plt.rc_context({"font.family": "sans-serif", "font.size": 10, "svg.fonttype": "path"}):
        fig, axes = plt.subplots(1, 2, figsize=(9.6, 5.2), sharey=True)
        for ax, col, metric, ref in zip(axes, ["tail_spread", "miss_skip_pct"], ["tail_spread", "miss_skip_pct"], [1, None]):
            ax.text(1.02, 1.0, "Holm p", transform=ax.transAxes, ha="left", va="bottom", fontsize=9, color=AXIS)
            for i, n in enumerate(names):
                if (n, metric) in tt.index:
                    r = tt.loc[(n, metric)]
                    ax.text(1.02, i, fmt_p(r.p_holm) + (" *" if r["significant_holm_0.05"] else ""), transform=ax.get_yaxis_transform(), ha="left", va="center",
                            fontsize=9.5, color=TEXT, fontweight="bold" if r["significant_holm_0.05"] else "normal", clip_on=False)
                g = sub[sub.configuration == n].sort_values("U")
                if g.empty:
                    continue
                x = g[col].to_numpy().astype(float)
                zero = col == "miss_skip_pct"
                xp = np.where(x <= 0, ZERO_X, x) if zero else x
                ax.plot([xp.min(), xp.max()], [i, i], color="#cfcfcf", lw=1.0, zorder=2)
                for u, xv, xr in zip(g.U, xp, x):
                    hollow = zero and xr <= 0
                    ax.plot(xv, i, "o", ms=8, mfc="white" if hollow else UCOL[u], mec=UCOL[u] if hollow else "white", mew=1.5, zorder=3)
                mx = x.max()
                if (col == "tail_spread" and mx >= 1.5) or (col == "miss_skip_pct" and mx >= 0.25):
                    ax.annotate(f"{mx:#.3g}" if col == "tail_spread" else f"{mx:.2f}", (max(xp), i), xytext=(7, 0), textcoords="offset points", va="center", ha="left", color=TEXT, fontsize=9)
            if ref is not None:
                ax.axvline(ref, color="#6b6a66", lw=1.0, ls=(0, (4, 3)), zorder=1)
            ax.set_xscale("log")
            ax.grid(axis="x", color=GRID, lw=0.8, zorder=0); ax.set_axisbelow(True)
            for s in ("top", "right", "left"):
                ax.spines[s].set_visible(False)
            ax.spines["bottom"].set_color(AXIS)
            ax.tick_params(colors=AXIS, length=3); ax.tick_params(axis="y", length=0)
        axes[0].set_xlim(*xl_s)
        ts = [t for t in [1, 2, 5, 10, 20, 50] if xl_s[0] <= t <= xl_s[1]]
        axes[0].set_xticks(ts); axes[0].set_xticklabels([f"{x:g}" for x in ts]); axes[0].minorticks_off()
        axes[1].set_xlim(*xl_m)
        tm = [ZERO_X, 0.01, 0.1, 1, 10]
        axes[1].set_xticks(tm); axes[1].set_xticklabels(["0", "0.01", "0.1", "1", "10"]); axes[1].minorticks_off()
        axes[0].set_ylim(len(names) - 0.4, -0.6)
        axes[0].set_yticks(range(len(names))); axes[0].set_yticklabels([cm.FIG_LABEL[n] for n in names], color=TEXT)
        axes[0].set_xlabel("tail spread $S = p_{99.9}\\,/\\,\\mathrm{median}$", color=TEXT)
        axes[1].set_xlabel("miss+skip rate [%] (log axis; open marker = 0)", color=TEXT)
        handles = [Line2D([], [], marker="o", ls="", ms=8, mfc=UCOL[u], mec="white", mew=1.5, label=f"U = {u:g}") for u in cm.UTILS]
        fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.925), labelcolor=TEXT, handletextpad=0.1, columnspacing=1.2, fontsize=10)
        fig.suptitle(f"{ptitle}, {sslug} period (P = {P} ms)", x=0.01, ha="left", y=0.985, fontsize=12, fontweight="bold", color=TEXT)
        fig.subplots_adjust(left=0.24, right=0.875, top=0.80, bottom=0.14, wspace=0.42)
        for ext, kw in (("svg", {}), ("png", {"dpi": 200})):
            fig.savefig(cm.OUT / f"rq1_{pslug}_{sslug}.{ext}", facecolor="white", **kw)
        plt.close(fig)


HM_COLS = [(s, u) for s, _, _ in cm.SCALES for u in cm.UTILS]


def heatmap(v, place, stem, valcol, color_fn, shown_fn, cbar_label, tick_pos, tick_labels):
    tab = v[v.placement == place].set_index(["configuration", "scale", "U"])
    cell_w, row_h, gap, label_w = 1.0, 1.0, 0.55, 4.6
    xs = {c: i + (gap if i >= len(cm.UTILS) else 0) for i, c in enumerate(HM_COLS)}
    configs = cm.CONFIGS
    ypos = {c: 2.4 + i * row_h for i, c in enumerate(configs)}
    total_h = 2.4 + len(configs) * row_h + 0.2
    width_in = 12.5 / 2.54
    unit_in = width_in / (label_w + len(HM_COLS) + gap + 0.2)
    height_in = total_h * unit_in * 0.62 + 0.75
    with plt.rc_context({"font.size": 7, "font.family": "serif", "svg.fonttype": "path"}):
        fig = plt.figure(figsize=(width_in, height_in))
        ax = fig.add_axes([0.0, 0.75 / height_in, 1.0, 1 - 0.75 / height_in])
        ax.set_xlim(-label_w, len(HM_COLS) + gap + 0.2); ax.set_ylim(total_h, 0); ax.axis("off")
        ax.text(-label_w + 0.1, 0.55, place, ha="left", va="center", fontsize=8, fontweight="bold")
        for scale, _, title in cm.SCALES:
            cols = [c for c in HM_COLS if c[0] == scale]
            x0, x1 = xs[cols[0]], xs[cols[-1]] + cell_w
            ax.text((x0 + x1) / 2, 0.55, title, ha="center", va="center", fontsize=8, fontweight="bold")
            ax.plot([x0 + 0.05, x1 - 0.05], [1.05, 1.05], color="black", lw=0.7)
            for c in cols:
                ax.text(xs[c] + cell_w / 2, 1.75, f"{c[1]:g}", ha="center", va="center", fontsize=7)
        ax.text(-label_w + 0.1, 1.75, "$U$", ha="left", va="center", fontsize=7, style="italic")
        for config in configs:
            yy = ypos[config]
            ax.text(-0.12, yy + row_h / 2, config, ha="right", va="center", fontsize=6.8)
            for c in HM_COLS:
                x0 = xs[c]
                if not cm.planned(config, c[1]):
                    ax.add_patch(plt.Rectangle((x0, yy), cell_w, row_h, facecolor="white", edgecolor="#aaaaaa", linewidth=0.5, hatch="////", zorder=1))
                    ax.text(x0 + cell_w / 2, yy + row_h / 2, "n/r", ha="center", va="center", fontsize=5, color="#555555", zorder=3, bbox=dict(facecolor="white", edgecolor="none", pad=0.4))
                    continue
                r = tab.loc[(config, c[0], c[1])]
                rgba = RED_BLACK(color_fn(r[valcol]))
                lum = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                ax.add_patch(plt.Rectangle((x0, yy), cell_w, row_h, facecolor=rgba, edgecolor="#d9d9d9", linewidth=0.5))
                ax.text(x0 + cell_w / 2, yy + row_h / 2, shown_fn(r[valcol]), ha="center", va="center", fontsize=6.0, color="white" if lum < 0.45 else "#1a1a1a")
        cax = fig.add_axes([0.30, 0.46 / height_in, 0.66, 0.13 / height_in])
        cax.imshow(np.linspace(0, 1, 512)[None, :], aspect="auto", cmap=RED_BLACK, extent=[0, 1, 0, 1])
        cax.set_xticks(tick_pos); cax.set_xticklabels(tick_labels, fontsize=7)
        cax.set_yticks([])
        cax.set_xlabel(cbar_label, fontsize=7.5, labelpad=2)
        for s in cax.spines.values():
            s.set_linewidth(0.5)
        fig.savefig(cm.OUT / f"{stem}.png", dpi=300)
        fig.savefig(cm.OUT / f"{stem}.svg")
    plt.close(fig)


def main():
    v = cell_values()
    tests = pd.read_csv(cm.OUT / "step3_tests.csv")
    xl_s = (0.9, max(70.0, v.tail_spread.max() * 1.6))
    pos = v.miss_skip_pct[v.miss_skip_pct > 0]
    xl_m = (ZERO_X / 1.7, max(30.0, v.miss_skip_pct.max() * 2.0))
    for place, pslug, ptitle, *_ in cm.PLACEMENTS:
        for scale, P, _ in cm.SCALES:
            figure(v, tests, place, pslug, ptitle, scale, scale, P // 1000, xl_s, xl_m)
    # worst window: loss fraction (k - m) / k on a square-root scale, as in the existing heatmap
    for place in cm.PLACE_NAMES:
        heatmap(v, place, f"heatmap_worst_window_{place}", "m_worst_round",
                lambda m: float(np.sqrt((cm.K_WINDOW - m) / cm.K_WINDOW)), lambda m: f"{int(m)}",
                "Loss in worst window ($k = 100$ releases; worst of 4 rounds)",
                [float(np.sqrt(x)) for x in [0, 0.10, 0.25, 0.50, 0.75, 1.0]], [f"{int(x * 100)}%" for x in [0, 0.10, 0.25, 0.50, 0.75, 1.0]])
    vmax = float(v.longest_run_max_round.max())
    ticks = [t for t in [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000] if t <= vmax]
    if ticks[-1] != vmax:
        ticks.append(vmax)
    for place in cm.PLACE_NAMES:
        heatmap(v, place, f"heatmap_longest_run_{place}", "longest_run_max_round",
                lambda x: float(np.sqrt(x / vmax)) if vmax > 0 else 0.0, lambda x: f"{int(x)}",
                "Longest run of consecutive lost releases (largest of 4 rounds)",
                [float(np.sqrt(t / vmax)) for t in ticks], [f"{int(t)}" for t in ticks])
    print(f"figures: {len(v)} cells; S max {v.tail_spread.max():.2f}, M max {v.miss_skip_pct.max():.3f}%, longest run max {int(vmax)}")
    return 0


if __name__ == "__main__":
    main()
