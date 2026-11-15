#!/usr/bin/env python3
"""Longest run of consecutive lost releases per configuration, utilization and period (read-only on the frozen data).

    python3 make_rq1_consecutive.py

A release is lost when its job missed the deadline (R > D) or it was skipped after an overrun (column skipped_before of the job that
caused it; the skipped releases sit right after that job). Release sequence per round (and per target thread where the file has a
`thread` column: the multi-core full-isolation runs have two), so runs never join across rounds or threads. Same data, configurations
and warm-up (first N_DROP = 6 jobs of every round, with the releases skipped after them) as make_results_final.py.
Value drawn = longest run of consecutive lost releases in the cell (max over rounds/threads); 0 = no release lost.
Writes rq1_consecutive_{singlecore,multicore}.{svg,png} and rq1_consecutive_values.csv next to this script.
"""
import pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = pathlib.Path(__file__).resolve().parent
OS_DATA = HERE.parent.parent / "analysis" / "data"
BASE_DATA = HERE.parent.parent.parent / "kubedeadline-experiments" / "analysis" / "data"
FULL = "full isolation"
SCEN = [("01", "isolcpus"), ("02", "nohz_full"), ("03", "rcu_nocbs"), ("04", "systemd containment"),
        ("05", "IRQ steering"), ("08", "frequency pinning"), ("06", "boot-params bundle")]
PLACEMENTS = [("single-core", "singlecore", "Single-core", "model1", "model1"), ("multi-core", "multicore", "Multi-core", "model5", "model5-phys")]
SCALES = [("tight", "Tight period (P = 10 ms)"), ("soft", "Soft period (P = 100 ms)")]
UTILS = [0.1, 0.5, 0.7, 0.94]
N_DROP = 6
NAMES = [FULL] + [n + " reverted" for _, n in SCEN]
COLORS = ["#7f7f7f", "#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#8c564b"]   # full isolation grey, then one colour per lever
AXIS, TEXT, GRID = "#52514e", "#0b0b0b", "#e1e0d9"


def longest_run(g):
    best = 0
    keys = ["round"] + (["thread"] if "thread" in g.columns else [])
    for _, rg in g.groupby(keys, sort=False):
        rg = rg.sort_values("job_index")
        lost = rg.deadline_miss.to_numpy(dtype=int)
        extra = rg.skipped_before.to_numpy(dtype=int)
        seq = np.zeros(len(lost) + extra.sum(), dtype=np.int8)
        pos = np.arange(len(lost)) + np.r_[0, np.cumsum(extra)[:-1]]
        seq[pos] = lost
        for p, e in zip(pos, extra):
            seq[p + 1:p + 1 + e] = 1
        cur = 0
        for v in seq:
            cur = cur + 1 if v else 0
            best = max(best, cur)
    return best


def compute(model, base):
    rows = []
    srcs = [(NAMES[0], BASE_DATA / f"{base}.csv")] + [(n + " reverted", OS_DATA / f"{c}-{model}.csv") for c, n in SCEN]
    for name, path in srcs:
        df = pd.read_csv(path)
        for (scale, u), g in df.groupby(["scale", "U"]):
            if u in UTILS:
                g = g[g.job_index >= N_DROP]
                rows.append(dict(configuration=name, scale=scale, U=u, longest_run=longest_run(g), lost=int(g.deadline_miss.sum() + g.skipped_before.sum())))
    return pd.DataFrame(rows)


def figure(t, place, pslug, ptitle, ymax):
    with plt.rc_context({"font.family": "sans-serif", "font.size": 10, "svg.fonttype": "path"}):
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), sharey=True)
        w = 0.1
        for ax, (scale, stitle) in zip(axes, SCALES):
            for k, name in enumerate(NAMES):
                for i, u in enumerate(UTILS):
                    r = t[(t.configuration == name) & (t.scale == scale) & (t.U == u)]
                    if r.empty:
                        continue                                   # cell not run
                    v = int(r.longest_run.iloc[0])
                    x = i + (k - (len(NAMES) - 1) / 2) * w
                    ax.bar(x, v, width=w * 0.92, color=COLORS[k], zorder=3)
                    inside = v >= 0.3 * ymax
                    ax.text(x, v / 2 if inside else v + 0.01 * ymax, str(v), ha="center", va="center" if inside else "bottom", rotation=90,
                            fontsize=8.5, color="white" if inside else TEXT, zorder=4)
            ax.set_xticks(range(len(UTILS))); ax.set_xticklabels([f"{u:g}" for u in UTILS])
            ax.set_xlabel("Utilization $U$", color=TEXT)
            ax.set_title(stitle, loc="left", fontsize=11, fontweight="bold", color=TEXT)
            ax.set_ylim(0, ymax)
            ax.grid(axis="y", color=GRID, lw=0.8, zorder=0); ax.set_axisbelow(True)
            for s in ("top", "right", "left"):
                ax.spines[s].set_visible(False)
            ax.spines["bottom"].set_color(AXIS)
            ax.tick_params(colors=AXIS, length=3); ax.tick_params(axis="y", length=0)
        axes[0].set_ylabel("longest run of consecutive lost releases", color=TEXT)
        fig.legend(handles=[Patch(color=COLORS[k], label=n) for k, n in enumerate(NAMES)], loc="upper center", ncol=4, frameon=False, labelcolor=TEXT,
                   bbox_to_anchor=(0.5, 0.995), fontsize=9.5)
        fig.subplots_adjust(left=0.07, right=0.995, top=0.78, bottom=0.12, wspace=0.05)
        for ext, kw in (("svg", {}), ("png", {"dpi": 200})):
            fig.savefig(HERE / f"rq1_consecutive_{pslug}.{ext}", facecolor="white", **kw)
        plt.close(fig)


res = {p[0]: compute(p[3], p[4]).assign(placement=p[0]) for p in PLACEMENTS}
allv = pd.concat(res.values())
allv.to_csv(HERE / "rq1_consecutive_values.csv", index=False)
print(allv.pivot_table(index=["placement", "scale", "U"], columns="configuration", values="longest_run")[NAMES].to_string())
ymax = float(allv.longest_run.max()) * 1.08                         # same y limit in all figures
for place, pslug, ptitle, *_ in PLACEMENTS:
    figure(res[place], place, pslug, ptitle, ymax)
