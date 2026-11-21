#!/usr/bin/env python3
"""Longest run of consecutive lost releases per configuration, utilization and period (read-only on the frozen data).

    python3 make_rq1_consecutive.py

A release is lost when its job missed the deadline (R > D) or it was skipped after an overrun (column skipped_before of the job that
caused it; the skipped releases sit right after that job). Release sequence per round (and per target thread where the file has a
`thread` column: the multi-core full-isolation runs have two), so runs never join across rounds or threads. Same data, configurations
and warm-up (first N_DROP = 6 jobs of every round, with the releases skipped after them) as make_results_final.py.
Value drawn = longest run of consecutive lost releases in the cell (max over rounds/threads); 0 = no release lost.
Drawn as an annotated grid (rows = configuration, columns = period x U). Writes rq1_consecutive_{singlecore,multicore}.{svg,png} and rq1_consecutive_values.csv next to this script.
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
        ("05", "IRQ steering"), ("08", "frequency pinning"), ("06", "boot-params bundle"), ("07", "all defaults")]
PLACEMENTS = [("single-core", "singlecore", "Single-core", "model1", "model1"), ("multi-core", "multicore", "Multi-core", "model5", "model5-phys")]
SCALES = [("tight", "Tight period (P = 10 ms)"), ("soft", "Soft period (P = 100 ms)")]
UTILS = [0.1, 0.5, 0.7, 0.94]
N_DROP = 6
PINNED = "pinned tasks"
NAMES = [FULL] + [n if n == "all defaults" else n + " reverted" for _, n in SCEN]
COLORS = ["#7f7f7f", "#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#8c564b", "#F0E442"]   # full isolation grey, then one colour per lever
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
    srcs = [(NAMES[0], BASE_DATA / f"{base}.csv")] + [(n if n == "all defaults" else n + " reverted", OS_DATA / f"{c}-{model}.csv") for c, n in SCEN]
    if model == "model5":                                           # multi-core only: full isolation with each task pinned to one reserved cpu
        srcs.append((PINNED, BASE_DATA / "model5-phys-pinned.csv"))
    for name, path in srcs:
        df = pd.read_csv(path)
        for (scale, u), g in df.groupby(["scale", "U"]):
            if u in UTILS:
                g = g[g.job_index >= N_DROP]
                rows.append(dict(configuration=name, scale=scale, U=u, longest_run=longest_run(g), lost=int(g.deadline_miss.sum() + g.skipped_before.sum())))
    return pd.DataFrame(rows)


def figure(t, place, pslug, ptitle, vmax):
    NAMES = ALLNAMES + ([PINNED] if place == "multi-core" else [])
    """one annotated grid per placement: rows = configuration, columns = period x U; colour ~ log(1 + value), number = longest run."""
    from matplotlib.colors import LogNorm, ListedColormap
    cols = [(sc, u) for sc, _ in SCALES for u in UTILS]
    val = np.full((len(NAMES), len(cols)), np.nan)
    for k, name in enumerate(NAMES):
        for c, (sc, u) in enumerate(cols):
            r = t[(t.configuration == name) & (t.scale == sc) & (t.U == u)]
            if not r.empty:
                val[k, c] = r.longest_run.iloc[0]
    with plt.rc_context({"font.family": "sans-serif", "font.size": 10, "svg.fonttype": "path"}):
        fig, ax = plt.subplots(figsize=(9.5, 4.6))
        cmap = plt.get_cmap("Blues").copy(); cmap.set_bad("#f0efe9")
        ax.imshow(np.ma.masked_invalid(val + 1), cmap=cmap, norm=LogNorm(1, vmax + 1), aspect="auto")
        for k in range(len(NAMES)):
            for c in range(len(cols)):
                v = val[k, c]
                if np.isnan(v):
                    ax.text(c, k, "n/r", ha="center", va="center", color=AXIS, fontsize=9)
                else:
                    ax.text(c, k, f"{int(v)}", ha="center", va="center", fontsize=10.5, fontweight="bold" if v > 0 else "normal",
                            color="white" if (v + 1) > (vmax + 1) ** 0.55 else TEXT)
        ax.set_xticks(range(len(cols))); ax.set_xticklabels([f"{u:g}" for _, u in cols])
        ax.set_yticks(range(len(NAMES))); ax.set_yticklabels(NAMES)
        ax.set_xlabel("Utilization $U$", color=TEXT)
        ax.axvline(len(UTILS) - 0.5, color="white", lw=6)
        for k in range(len(NAMES) + 1):
            ax.axhline(k - 0.5, color="white", lw=1.5)
        for q, (sc, st) in enumerate(SCALES):
            ax.text((q + 0.5) * len(UTILS) - 0.5, -0.75, st, ha="center", va="bottom", fontsize=11, fontweight="bold", color=TEXT)
        ax.axhline(0.5, color=AXIS, lw=1.2)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(colors=AXIS, length=0)
        fig.text(0.01, 0.01, "Number = longest run of consecutive lost releases in the cell (0 = none lost); n/r = not run. Colour on a log scale, shared by all figures.",
                 fontsize=8, color=AXIS)
        fig.subplots_adjust(left=0.27, right=0.99, top=0.9, bottom=0.17)
        for ext, kw in (("svg", {}), ("png", {"dpi": 200})):
            fig.savefig(HERE / f"rq1_consecutive_{pslug}.{ext}", facecolor="white", **kw)
        plt.close(fig)


ALLNAMES = NAMES
res = {p[0]: compute(p[3], p[4]).assign(placement=p[0]) for p in PLACEMENTS}
allv = pd.concat(res.values())
allv.to_csv(HERE / "rq1_consecutive_values.csv", index=False)
print(allv.pivot_table(index=["placement", "scale", "U"], columns="configuration", values="longest_run")[NAMES].to_string())
ymax = float(allv.longest_run.max())                               # same colour scale in all figures
for place, pslug, ptitle, *_ in PLACEMENTS:
    figure(res[place], place, pslug, ptitle, ymax)
