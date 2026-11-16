#!/usr/bin/env python3
"""PLATFORM figures. Needs output/platform/platform_run_metrics.csv (run platform_effects.py first).

One figure per placement x period: output/platform/platform_{singlecore,multicore}_{tight,soft}.{pdf,png}; the main-text one is single-core, P = 10 ms.
One row of panels per metric (miss+skip rate, dispatch latency p99, CV of C, jobs with mid-job preemption > 10 us, jobs with an involuntary switch), absolute units.
  left column   within-round difference to full isolation (configuration minus full isolation, same round), one row per configuration (full isolation is the
                reference, not drawn), one dot per round (marker shape = round), line at 0; the four U are offset vertically inside a row, colour = U.
  right column  value of the metric per round (one row per round); all configurations as small dots (colour = U), full isolation as a large open diamond.
Configuration order and the U colour ramp are those of the existing RQ1 figures. No ratios. Axis limits are set per figure (placement x period).
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import common as cm
from platform_effects import METRICS, OUTP

UCOL = {0.1: "#9ec5f4", 0.5: "#5598e7", 0.7: "#256abf", 0.94: "#0d366b"}
UOFF = {0.1: -0.27, 0.5: -0.09, 0.7: 0.09, 0.94: 0.27}
RMARK = {1: "o", 2: "s", 3: "^", 4: "D"}
AXIS, TEXT, GRID = "#52514e", "#0b0b0b", "#e1e0d9"
UNIT = {"miss_skip_pct": "%", "dispatch_p99_us": "$\\mu$s", "cv_C_pct": "%", "interrupted_jobs_pct": "%", "switched_jobs_pct": "%"}
SHORT = {"miss_skip_pct": "miss+skip rate", "dispatch_p99_us": "dispatch latency p99", "cv_C_pct": "CV of $C$",
         "interrupted_jobs_pct": "jobs with preemption > 10 $\\mu$s", "switched_jobs_pct": "jobs with involuntary switch"}


def prep():
    t = pd.read_csv(OUTP / "platform_run_metrics.csv")
    fi = t[t.configuration == cm.FULL].set_index(["placement", "scale", "U", "round"])
    key = list(zip(t.placement, t.scale, t.U, t["round"]))
    d = t.copy()
    for m, _ in METRICS:
        d[m + "_diff"] = t[m].to_numpy() - fi[m].reindex(key).to_numpy()
    return d


def limits(d):
    lim = {}
    for m, _ in METRICS:
        x = d[d.configuration != cm.FULL][m + "_diff"].dropna()
        pad = 0.06 * (x.max() - x.min())
        a = d[m].dropna()
        lim[m] = dict(diff=(x.min() - pad, x.max() + pad), val=(max(0.0, a.min() - 0.04 * (a.max() - a.min())), a.max() + 0.06 * (a.max() - a.min())))
    return lim


def style(ax):
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0); ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=AXIS, length=3); ax.tick_params(axis="y", length=0)


def figure(d, lim, pl, pslug, ptitle, scale, P):
    sub = d[(d.placement == pl) & (d.scale == scale)]
    cfgs = cm.CONFIGS[1:]
    with plt.rc_context({"font.family": "sans-serif", "font.size": 10, "svg.fonttype": "path", "pdf.fonttype": 42}):
        fig, axes = plt.subplots(len(METRICS), 2, figsize=(12.6, 15.5), gridspec_kw=dict(width_ratios=[1.35, 1.0]))
        for r, (m, _) in enumerate(METRICS):
            axl, axr = axes[r]
            for i, c in enumerate(cfgs):                                         # left: within-round difference to full isolation
                for u in cm.UTILS:
                    if not cm.planned(c, u):
                        continue
                    for rd in cm.ROUNDS:
                        row = sub[(sub.configuration == c) & (sub.U == u) & (sub["round"] == rd)]
                        if len(row) and np.isfinite(row[m + "_diff"].iloc[0]):
                            axl.plot(row[m + "_diff"].iloc[0], i + UOFF[u], RMARK[rd], ms=4.6, mfc=UCOL[u], mec="white", mew=0.5, ls="", zorder=3)
            axl.axvline(0, color="#6b6a66", lw=1.0, ls=(0, (4, 3)), zorder=1)
            axl.set_xlim(*lim[m]["diff"]); axl.set_ylim(len(cfgs) - 0.4, -0.6)
            axl.set_yticks(range(len(cfgs))); axl.set_yticklabels([cm.FIG_LABEL[c] for c in cfgs], color=TEXT, fontsize=9)
            axl.set_xlabel(f"{SHORT[m]}: configuration $-$ full isolation, same round [{UNIT[m]}]", color=TEXT, fontsize=9)
            style(axl)
            for j, rd in enumerate(cm.ROUNDS):                                   # right: values per round
                for u in cm.UTILS:
                    y = j + UOFF[u]
                    g = sub[(sub.U == u) & (sub["round"] == rd) & (sub.configuration != cm.FULL)]
                    axr.plot(g[m], np.full(len(g), y), "o", ms=3.4, mfc=UCOL[u], mec="white", mew=0.3, ls="", zorder=3, alpha=0.95)
                    f = sub[(sub.U == u) & (sub["round"] == rd) & (sub.configuration == cm.FULL)]
                    axr.plot(f[m], np.full(len(f), y), "D", ms=6.4, mfc="white", mec=TEXT, mew=1.3, ls="", zorder=4)
            axr.set_xlim(*lim[m]["val"]); axr.set_ylim(len(cm.ROUNDS) - 0.4, -0.6)
            axr.set_yticks(range(len(cm.ROUNDS))); axr.set_yticklabels([f"round {rd}" for rd in cm.ROUNDS], color=TEXT, fontsize=9)
            axr.set_xlabel(f"{SHORT[m]} [{UNIT[m]}]", color=TEXT, fontsize=9)
            style(axr)
        hu = [Line2D([], [], marker="o", ls="", ms=7, mfc=UCOL[u], mec="white", mew=1.2, label=f"U = {u:g}") for u in cm.UTILS]
        hr = [Line2D([], [], marker=RMARK[rd], ls="", ms=6, mfc="#8a8a8a", mec="white", mew=0.8, label=f"round {rd}") for rd in cm.ROUNDS]
        hf = [Line2D([], [], marker="D", ls="", ms=7, mfc="white", mec=TEXT, mew=1.3, label="full isolation")]
        fig.legend(handles=hu + hr + hf, loc="upper center", ncol=9, frameon=False, bbox_to_anchor=(0.5, 0.972), labelcolor=TEXT, handletextpad=0.1, columnspacing=1.0, fontsize=9)
        fig.suptitle(f"Configuration and round effects: {ptitle}, P = {P} ms", x=0.01, ha="left", y=0.995, fontsize=12, fontweight="bold", color=TEXT)
        fig.subplots_adjust(left=0.185, right=0.985, top=0.94, bottom=0.035, wspace=0.28, hspace=0.50)
        for ext, kw in (("pdf", {}), ("png", {"dpi": 160})):
            fig.savefig(OUTP / f"platform_{pslug}_{scale}.{ext}", facecolor="white", **kw)
        plt.close(fig)


def main():
    d = prep()
    for pl, pslug, ptitle, *_ in cm.PLACEMENTS:
        for s, P, _ in cm.SCALES:
            figure(d, limits(d[(d.placement == pl) & (d.scale == s)]), pl, pslug, ptitle, s, P // 1000)
    cap = []
    for pl, pslug, ptitle, *_ in cm.PLACEMENTS:
        for s, P, _ in cm.SCALES:
            cap.append(r"\caption{Configuration and round effects, " + f"{pl}, $P = {P // 1000}$ ms. " +
                       r"Left: difference between a configuration and full isolation within the same round, one dot per round (marker shape), colour = utilization, absolute units; "
                       r"the line marks 0. Right: value of the metric in every round; small dots are the configurations, the open diamond is full isolation. "
                       r"Dispatch latency excludes jobs with $C > Q$; cells not run are omitted.}")
    (OUTP / "platform_captions.tex").write_text("\n\n".join(cap) + "\n")
    print("platform figures written (4, pdf+png)")
    return 0


if __name__ == "__main__":
    main()
