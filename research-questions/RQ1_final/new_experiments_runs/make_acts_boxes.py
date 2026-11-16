#!/usr/bin/env python3
"""'Where each configuration acts' figures (box and bar version), rerun data only.

    ../.venv/bin/python make_acts_boxes.py

One figure per placement x period: output/acts_{singlecore,multicore}_{tight,soft}.{pdf,png} (single-core tight is the main-text figure, the other
three are for the appendix). Two rows of panels, U = 0.1 (top) and U = 0.5 (bottom); configurations on the y axis in the fixed order, full isolation first.
  panel 1  box plot of C_cputime_us / median C of full isolation (same placement, period, U; all rounds pooled); linear x, dashed line at 1
  panel 2  box plot of dispatch_latency_us, log x; jobs with C > Q excluded (Q = U * P)
  panel 3  bar = interrupted jobs per second of execution (mid_job_preempt_us > 10 us; jobs with C > Q excluded), all rounds pooled; one small dot per round; log x with a zero position
  panel 4  bar = involuntary context switches per second of execution (all jobs), same treatment as panel 3
Box = p25-p75, line = median, whiskers = p1-p99, small marker = p99.9, no outlier points. The four rounds are pooled in every box. Execution time of a job = finish - start.
The x limits of a panel are the same in both rows and in all four figures. Writes output/acts_box_values.csv and output/acts_captions.tex.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import common as cm

ROWS_U = [0.1, 0.5]
UCOL = {0.1: "#9ec5f4", 0.5: "#5598e7"}
AXIS, TEXT, GRID, DARK = "#52514e", "#0b0b0b", "#e1e0d9", "#1f2a3a"
PCT = [1, 25, 50, 75, 99, 99.9]


def stats():
    runs, _ = cm.get_runs()
    out = {}
    for pl in cm.PLACE_NAMES:
        for s, P, _ in cm.SCALES:
            for u in ROWS_U:
                Q = u * P
                fiC = np.concatenate([runs[(pl, cm.FULL, s, u, r)]["C_cputime_us"] for r in cm.ROUNDS])
                med_fi = float(np.median(fiC))
                for c in cm.CONFIGS:
                    rr = [runs[(pl, c, s, u, r)] for r in cm.ROUNDS]
                    C = np.concatenate([a["C_cputime_us"] for a in rr])
                    keep = [a["C_cputime_us"] <= Q for a in rr]
                    disp = np.concatenate([a["dispatch_latency_us"][k] for a, k in zip(rr, keep)])
                    ex = [(a["finish_us"] - a["start_us"]) for a in rr]
                    n_int = [int((a["mid_job_preempt_us"][k] > cm.INTERRUPT_US).sum()) for a, k in zip(rr, keep)]
                    t_int = [float(e[k].sum() / 1e6) for e, k in zip(ex, keep)]
                    n_cs = [float(a["nonvol_ctxt"].sum()) for a in rr]
                    t_all = [float(e.sum() / 1e6) for e in ex]
                    out[(pl, s, u, c)] = dict(
                        c_pct=np.percentile(C / med_fi, PCT), d_pct=np.percentile(disp, PCT), med_fi=med_fi,
                        int_pool=sum(n_int) / sum(t_int), int_round=[n / t for n, t in zip(n_int, t_int)],
                        cs_pool=sum(n_cs) / sum(t_all), cs_round=[n / t for n, t in zip(n_cs, t_all)],
                        n_jobs=len(C), n_C_gt_Q=int(sum((~k).sum() for k in keep)))
    return out


def limits(st):
    c = np.array([v["c_pct"] for v in st.values()])
    d = np.array([v["d_pct"] for v in st.values()])
    lim = {"c": (c[:, 0].min() - 0.03, c[:, -1].max() + 0.08), "d": (d[:, 0].min() / 1.3, d[:, -1].max() * 1.5)}
    for key, pool, rnd in (("i", "int_pool", "int_round"), ("s", "cs_pool", "cs_round")):
        vals = np.array([x for v in st.values() for x in [v[pool]] + list(v[rnd])])
        pos = vals[vals > 0]
        z = pos.min() / 4.0
        lim[key] = (z / 1.6, vals.max() * 2.5)
        lim[key + "z"] = z
    return lim


def decade_ticks(xlim, lo=None):
    return [10.0 ** e for e in range(-5, 7) if xlim[0] <= 10.0 ** e <= xlim[1] and (lo is None or 10.0 ** e >= lo)]


def draw_box(ax, i, p, color):
    p1, p25, p50, p75, p99, p999 = p
    h = 0.5
    ax.plot([p1, p25], [i, i], color=AXIS, lw=1.0, zorder=2)
    ax.plot([p75, p99], [i, i], color=AXIS, lw=1.0, zorder=2)
    for x in (p1, p99):
        ax.plot([x, x], [i - 0.14, i + 0.14], color=AXIS, lw=1.0, zorder=2)
    ax.add_patch(plt.Rectangle((p25, i - h / 2), max(p75 - p25, 1e-12), h, facecolor=color, edgecolor=AXIS, lw=0.9, zorder=3))
    ax.plot([p50, p50], [i - h / 2, i + h / 2], color=TEXT, lw=1.6, zorder=4)
    ax.plot(p999, i, marker="D", ms=3.6, mfc=DARK, mec="white", mew=0.5, ls="", zorder=5)


def draw_bar(ax, i, pool, rnd, z, color):
    if pool > 0:
        ax.barh(i, pool - z, left=z, height=0.5, color=color, edgecolor=AXIS, lw=0.6, zorder=3)
    else:
        ax.plot(z, i, "o", ms=6, mfc="white", mec=AXIS, mew=1.2, zorder=4)
    for v in rnd:
        ax.plot(z if v <= 0 else v, i, "o", ms=3.4, mfc=DARK, mec="white", mew=0.5, ls="", zorder=5)


def figure(st, lim, pl, pslug, ptitle, scale, P):
    names = cm.CONFIGS
    with plt.rc_context({"font.family": "sans-serif", "font.size": 10, "svg.fonttype": "path", "pdf.fonttype": 42}):
        fig, axes = plt.subplots(2, 4, figsize=(13.6, 8.6), sharey=True, sharex="col")
        for r, u in enumerate(ROWS_U):
            for k, key in enumerate("cdis"):
                ax = axes[r, k]
                for i, n in enumerate(names):
                    v = st[(pl, scale, u, n)]
                    if key == "c":
                        draw_box(ax, i, v["c_pct"], UCOL[u])
                    elif key == "d":
                        draw_box(ax, i, v["d_pct"], UCOL[u])
                    elif key == "i":
                        draw_bar(ax, i, v["int_pool"], v["int_round"], lim["iz"], UCOL[u])
                    else:
                        draw_bar(ax, i, v["cs_pool"], v["cs_round"], lim["sz"], UCOL[u])
                if key == "c":
                    ax.axvline(1, color="#6b6a66", lw=1.0, ls=(0, (4, 3)), zorder=1)
                    ax.set_xlim(*lim["c"])
                else:
                    ax.set_xscale("log"); ax.set_xlim(*lim[key])
                    if key == "d":
                        ts = [t for t in (20, 50, 100, 200, 500, 1000) if lim["d"][0] <= t <= lim["d"][1]]
                        ax.set_xticks(ts); ax.set_xticklabels([f"{t:g}" for t in ts])
                    else:
                        z = lim[key + "z"]
                        ts = decade_ticks(lim[key], lo=z * 10)
                        ax.set_xticks([z] + ts); ax.set_xticklabels(["0"] + [f"{t:g}" for t in ts])
                    ax.minorticks_off()
                ax.grid(axis="x", color=GRID, lw=0.8, zorder=0); ax.set_axisbelow(True)
                for s in ("top", "right", "left"):
                    ax.spines[s].set_visible(False)
                ax.spines["bottom"].set_color(AXIS)
                ax.tick_params(colors=AXIS, length=3, labelbottom=True); ax.tick_params(axis="y", length=0)
            axes[r, 0].text(0.0, 1.02, f"U = {u:g}", transform=axes[r, 0].transAxes, ha="left", va="bottom", fontsize=11, fontweight="bold", color=TEXT)
        axes[0, 0].set_ylim(len(names) - 0.4, -0.6)
        for r in range(2):
            axes[r, 0].set_yticks(range(len(names))); axes[r, 0].set_yticklabels([cm.FIG_LABEL[n] for n in names], color=TEXT)
        labels = ["$C$ / median $C$ of full isolation", "dispatch latency [$\\mu$s]", "interrupted jobs\nper second of execution", "involuntary context switches\nper second of execution"]
        for k in range(4):
            axes[1, k].set_xlabel(labels[k], color=TEXT)
        fig.suptitle(f"Where each configuration acts: {ptitle}, P = {P} ms", x=0.01, ha="left", y=0.985, fontsize=12, fontweight="bold", color=TEXT)
        fig.legend(handles=[Line2D([], [], marker="D", ls="", ms=4, mfc=DARK, mec="white", label="p99.9 (panels 1-2) / one round (panels 3-4)")],
                   loc="upper right", frameon=False, bbox_to_anchor=(0.995, 0.985), fontsize=9, labelcolor=TEXT)
        fig.subplots_adjust(left=0.20, right=0.995, top=0.90, bottom=0.10, wspace=0.10, hspace=0.20)
        for ext, kw in (("pdf", {}), ("png", {"dpi": 200})):
            fig.savefig(cm.OUT / f"acts_{pslug}_{scale}.{ext}", facecolor="white", **kw)
        plt.close(fig)


def main():
    st = stats()
    lim = limits(st)
    rows = []
    for (pl, s, u, c), v in st.items():
        d = dict(placement=pl, scale=s, U=u, configuration=c, n_jobs=v["n_jobs"], n_C_gt_Q=v["n_C_gt_Q"], median_C_full_isolation_us=v["med_fi"])
        for name, p in zip(["p1", "p25", "p50", "p75", "p99", "p99.9"], v["c_pct"]):
            d[f"C_over_medFI_{name}"] = p
        for name, p in zip(["p1", "p25", "p50", "p75", "p99", "p99.9"], v["d_pct"]):
            d[f"dispatch_us_{name}"] = p
        d["interrupted_jobs_per_s_pooled"] = v["int_pool"]
        d["nonvol_ctxt_per_s_pooled"] = v["cs_pool"]
        for r, (a, b) in enumerate(zip(v["int_round"], v["cs_round"]), 1):
            d[f"interrupted_jobs_per_s_round{r}"], d[f"nonvol_ctxt_per_s_round{r}"] = a, b
        rows.append(d)
    pd.DataFrame(rows).to_csv(cm.OUT / "acts_box_values.csv", index=False)
    caps = []
    for pl, pslug, ptitle, *_ in cm.PLACEMENTS:
        for s, P, _ in cm.SCALES:
            figure(st, lim, pl, pslug, ptitle, s, P // 1000)
            caps.append(r"\caption{Where each configuration acts, " + f"{pl}, $P = {P // 1000}$ ms, " + r"$U = 0.1$ (top) and $U = 0.5$ (bottom). "
                        r"Boxes pool the four rounds; box: $p_{25}$--$p_{75}$, line: median, whiskers: $p_1$--$p_{99}$, marker: $p_{99.9}$. "
                        r"Left: $C$ relative to the median $C$ of full isolation (same $U$, four rounds pooled); dashed line: 1. "
                        r"Second: dispatch latency, jobs with $C > Q$ excluded. Third: jobs per second of execution with mid-job preemption above $10\,\mu$s (jobs with $C > Q$ excluded); "
                        r"bar: four rounds pooled, dots: single rounds. Right: involuntary context switches per second of execution, same treatment. 0 marks no event.}")
    (cm.OUT / "acts_captions.tex").write_text("\n\n".join(caps) + "\n")
    print("acts box figures written (4 figures, pdf+png)")
    return 0


if __name__ == "__main__":
    main()
