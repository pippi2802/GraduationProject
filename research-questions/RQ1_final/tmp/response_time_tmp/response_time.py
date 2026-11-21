#!/usr/bin/env python3
"""Response time over time, frozen data, round 1: one panel per configuration, the four utilizations (0.1, 0.5, 0.7, 0.94) in one panel.
x = time since the first release of the run [s]; y = response time R_wall_us [ms], log axis; dashed line = deadline D = P.
First N_DROP = 6 jobs dropped (as in make_results_final.py). Multi-core full isolation / SMT have two target threads: thread 0 only.
Sources: os-experiments/analysis/data/<NN>-model{1,5}.csv, kubedeadline-experiments/analysis/data/{model1,model5-phys,model5-smt}.csv.
Writes response_time_{singlecore,multicore}_{tight,soft}.{png,svg}. Read-only on the data."""
import pathlib
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).resolve().parent
RQ1 = HERE.parent.parent
OLD, KD = RQ1 / "os-experiments" / "analysis" / "data", RQ1 / "kubedeadline-experiments" / "analysis" / "data"
ROUND, N_DROP = 1, 6
LEVERS = [("01", "isolcpus reverted"), ("02", "nohz_full reverted"), ("03", "rcu_nocbs reverted"), ("04", "systemd containment reverted"),
          ("05", "IRQ steering reverted"), ("08", "frequency pinning reverted"), ("06", "boot-params bundle reverted"), ("07", "all defaults")]
PLACE = [("single-core", "singlecore", "model1", "model1", []), ("multi-core", "multicore", "model5", "model5-phys", [("SMT enabled", KD / "model5-smt.csv")])]
PERIOD = {"tight": 10_000, "soft": 100_000}
UTILS = [0.1, 0.5, 0.7, 0.94]
UCOL = {0.1: "#9ec5f4", 0.5: "#4c8fe0", 0.7: "#e08a1e", 0.94: "#a3210f"}
COLS = ["job_index", "release_us", "R_wall_us", "round", "scale", "U"]


def load(path):
    head = pd.read_csv(path, nrows=0).columns
    d = pd.read_csv(path, usecols=COLS + (["thread"] if "thread" in head else []))
    if "thread" in d.columns:
        d = d[d.thread == d.thread.min()]
    return d[(d["round"] == ROUND) & d.U.isin(UTILS) & (d.job_index >= N_DROP)]


def main():
    for pl, slug, model, fi, extra in PLACE:
        srcs = [("full isolation", KD / f"{fi}.csv")] + [(n, OLD / f"{c}-{model}.csv") for c, n in LEVERS] + extra
        data = {n: load(p) for n, p in srcs}
        for scale in ("tight", "soft"):
            P = PERIOD[scale] / 1000.0
            nc = 3; nr = int(np.ceil(len(srcs) / nc))
            fig, axes = plt.subplots(nr, nc, figsize=(15, 3.4 * nr), sharex=True, sharey=True, squeeze=False)
            for ax in axes.ravel():
                ax.set_visible(False)
            for ax, (name, _) in zip(axes.ravel(), srcs):
                ax.set_visible(True)
                d = data[name][data[name].scale == scale]
                for u in UTILS:
                    g = d[d.U == u].sort_values("release_us")
                    if g.empty:
                        continue
                    ax.plot((g.release_us - g.release_us.iloc[0]) / 1e6, g.R_wall_us / 1000.0, ".", ms=1.6, alpha=0.7, color=UCOL[u], rasterized=True, label=f"U = {u:g}")
                ax.axhline(P, color="#52514e", ls="--", lw=0.9)
                ax.set_yscale("log"); ax.set_title(name, fontsize=11, fontweight="bold", loc="left"); ax.grid(color="#e1e0d9", lw=0.5)
                for s in ("top", "right"):
                    ax.spines[s].set_visible(False)
            for ax in axes[-1]:
                ax.set_xlabel("time since start of run [s]")
            for ax in axes[:, 0]:
                ax.set_ylabel("response time [ms]")
            h, l = axes[0, 0].get_legend_handles_labels()
            fig.legend(h, l, loc="upper center", ncol=4, frameon=False, markerscale=6, bbox_to_anchor=(0.5, 1.0))
            fig.suptitle(f"{pl}, {'tight P = 10 ms' if scale == 'tight' else 'soft P = 100 ms'}: response time over the run, round {ROUND} (dashed: deadline D = P)", y=1.03, fontsize=12)
            fig.tight_layout(rect=(0, 0, 1, 0.97))
            for ext, kw in (("png", {"dpi": 130}), ("svg", {})):
                fig.savefig(HERE / f"response_time_{slug}_{scale}.{ext}", facecolor="white", bbox_inches="tight", **kw)
            plt.close(fig)
            print("done", pl, scale)


main()
