#!/usr/bin/env python3
"""Where does the time of the slowest jobs go? (read-only on the frozen data)

    python3 make_rq1_tail_anatomy.py

Per cell (configuration, period, U): the slowest TAIL = 0.1 % of jobs by R_wall_us (pooled over rounds and, in the multi-core full-isolation file,
over both target threads; first N_DROP = 6 jobs of every round dropped, as in make_results_final.py). Mean over those jobs of
  execution      C_cputime_us
  dispatch       dispatch_latency_us          (release until the job first runs)
  off-CPU        mid_job_preempt_us           (after the first start: preempted by another task OR suspended by the reservation; not separable in the logs)
The three add up to the mean response time exactly (R = C + dispatch_latency + mid_job_preempt, checked below).
Budget Q = U * P. Per cell also: share of the tail jobs with C > Q, share of ALL jobs with C > Q (no selection), and the share of the tail's
dispatch time that comes from its single largest job (a few very late starts can dominate a 20-job mean). The same is computed for the slowest 1 %.
Drawn as a fraction of the period P: ticks = budget U, dashed line = deadline 1. Bars: execution at the bottom, then dispatch, then off-CPU.
Writes rq1_tail_anatomy_{singlecore,multicore}_{tight,soft}.{svg,png} and rq1_tail_anatomy_values.csv.
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
CODES = {"isolcpus": "01", "nohz_full": "02", "rcu_nocbs": "03", "systemd containment": "04", "IRQ steering": "05", "boot-params bundle": "06",
         "all defaults": "07", "frequency pinning": "08"}
PLACEMENTS = {"single-core": ("singlecore", "Single-core", "model1", "model1", [FULL, "isolcpus", "nohz_full", "systemd containment", "all defaults"]),
              "multi-core": ("multicore", "Multi-core", "model5", "model5-phys", [FULL, "SMT enabled", "rcu_nocbs", "all defaults", "pinned tasks"])}
PERIOD = {"tight": 10_000, "soft": 100_000}
UTILS = [0.1, 0.5, 0.7, 0.94]
N_DROP = 6
FRACS = (0.001, 0.01)
SEG = [("C_cputime_us", "execution", "#0072B2"), ("dispatch_latency_us", "dispatch (release until first run)", "#E69F00"),
       ("mid_job_preempt_us", "off-CPU after start (preempted or suspended by the reservation)", "#999999")]
AXIS, TEXT, GRID = "#52514e", "#0b0b0b", "#e1e0d9"


def cell_rows(df, config, place):
    rows = []
    for (scale, u), g in df.groupby(["scale", "U"]):
        if u not in UTILS:
            continue
        g = g[g.job_index >= N_DROP]
        P = PERIOD[scale]; Q = u * P
        assert np.abs(g.R_wall_us - g.C_cputime_us - g.dispatch_latency_us - g.mid_job_preempt_us).max() < 1e-3
        r = g.R_wall_us.to_numpy()
        for f in FRACS:
            t = g[r >= np.quantile(r, 1 - f)]
            d = t.dispatch_latency_us
            rows.append(dict(placement=place, configuration=config, scale=scale, U=u, tail_frac=f, n_tail=len(t), P_us=P, Q_us=Q,
                             exec_us=t.C_cputime_us.mean(), dispatch_us=d.mean(), offcpu_us=t.mid_job_preempt_us.mean(), R_us=t.R_wall_us.mean(),
                             median_exec_us=g.C_cputime_us.median(), tail_over_budget=float((t.C_cputime_us > Q).mean()),
                             all_over_budget=float((g.C_cputime_us > Q).mean()), dispatch_top_job_share=float(d.max() / d.sum()) if d.sum() > 0 else np.nan))
    return rows


def compute():
    rows = []
    for place, (_, _, model, base, cfgs) in PLACEMENTS.items():
        for c in cfgs:
            path = BASE_DATA / {"SMT enabled": "model5-smt.csv", "pinned tasks": "model5-phys-pinned.csv"}.get(c, f"{base}.csv") if c in (FULL, "SMT enabled", "pinned tasks") else OS_DATA / f"{CODES[c]}-{model}.csv"
            rows += cell_rows(pd.read_csv(path, usecols=["job_index", "R_wall_us", "C_cputime_us", "dispatch_latency_us", "mid_job_preempt_us", "scale", "U"]), c, place)
    return pd.DataFrame(rows)


def figure(t, place, scale):
    slug, title, _, _, cfgs = PLACEMENTS[place]
    sub = t[(t.placement == place) & (t.scale == scale) & (t.tail_frac == 0.001)]
    ymax = max(1.05, float((sub[[s[0].replace("C_cputime_us", "exec_us").replace("dispatch_latency_us", "dispatch_us").replace("mid_job_preempt_us", "offcpu_us")
                                 for s in SEG]].sum(axis=1) / sub.P_us).max()) * 1.12)
    CAP = 2.0                                                         # bars taller than this are cut and their total is written
    ymax = min(ymax, CAP)
    with plt.rc_context({"font.family": "sans-serif", "font.size": 10, "svg.fonttype": "path"}):
        fig, axes = plt.subplots(1, len(cfgs), figsize=(max(2.6 * len(cfgs) + 0.6, 10.5), 5.2), sharey=True)
        for ax, c in zip(axes, cfgs):
            for i, u in enumerate(UTILS):
                r = sub[(sub.configuration == c) & (sub.U == u)]
                if r.empty:
                    ax.text(i, 0.02 * ymax, "n/r", ha="center", va="bottom", fontsize=8, color=AXIS, rotation=90)
                    continue
                r = r.iloc[0]; bottom = 0.0
                for col, key, (_, lab, colr) in zip(("exec_us", "dispatch_us", "offcpu_us"), (0, 1, 2), SEG):
                    h = r[col] / r.P_us
                    ax.bar(i, h, bottom=bottom, width=0.7, color=colr, zorder=3); bottom += h
                ax.plot([i - 0.42, i + 0.42], [u, u], color="black", lw=1.6, zorder=5)                      # budget Q / P
                if bottom > ymax:                                              # cut bar: label inside the bar, with its total
                    ax.text(i, ymax * 1.10, f"{100 * r.tail_over_budget:.0f}%\n{bottom:.1f} P", ha="center", va="top", fontsize=8, color=TEXT,
                            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9), zorder=6)
                else:
                    ax.text(i, bottom + 0.015 * ymax, f"{100 * r.tail_over_budget:.0f}%", ha="center", va="bottom", fontsize=8.5, color=TEXT)
            ax.axhline(1.0, color="#b22222", ls="--", lw=1.1, zorder=4)
            ax.set_xticks(range(len(UTILS))); ax.set_xticklabels([f"{u:g}" for u in UTILS])
            ax.set_xlabel("Utilization $U$", color=TEXT)
            ax.set_title(c, fontsize=10.5, fontweight="bold", color=TEXT)
            ax.set_ylim(0, ymax * 1.12); ax.set_xlim(-0.6, len(UTILS) - 0.4)
            ax.grid(axis="y", color=GRID, lw=0.8, zorder=0); ax.set_axisbelow(True)
            for s in ("top", "right", "left"):
                ax.spines[s].set_visible(False)
            ax.spines["bottom"].set_color(AXIS); ax.tick_params(colors=AXIS, length=3); ax.tick_params(axis="y", length=0)
        axes[0].set_ylabel("slowest 0.1 % of jobs, mean, in periods $P$", color=TEXT)
        handles = [Patch(color=s[2], label=s[1]) for s in SEG] + [plt.Line2D([], [], color="black", lw=1.6, label="budget $Q = U P$"),
                                                                    plt.Line2D([], [], color="#b22222", ls="--", lw=1.1, label="deadline $D = P$")]
        fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False, labelcolor=TEXT, bbox_to_anchor=(0.5, 0.995), fontsize=9)
        fig.suptitle(f"{title}, {scale} period (P = {PERIOD[scale] // 1000} ms); number = share of those jobs with execution > Q (cut bars: number and total height inside)", fontsize=9.5, color=AXIS, y=0.80)
        fig.subplots_adjust(left=0.07, right=0.995, top=0.72, bottom=0.13, wspace=0.08)
        for ext, kw in (("svg", {}), ("png", {"dpi": 200})):
            fig.savefig(HERE / f"rq1_tail_anatomy_{slug}_{scale}.{ext}", facecolor="white", **kw)
        plt.close(fig)


t = compute()
t.to_csv(HERE / "rq1_tail_anatomy_values.csv", index=False, float_format="%.6g")
for place in PLACEMENTS:
    for scale in PERIOD:
        figure(t, place, scale)
pd.set_option("display.width", 250)
print(t[t.tail_frac == 0.001][["placement", "configuration", "scale", "U", "n_tail", "exec_us", "dispatch_us", "offcpu_us", "tail_over_budget", "all_over_budget", "dispatch_top_job_share"]].round(2).to_string())
