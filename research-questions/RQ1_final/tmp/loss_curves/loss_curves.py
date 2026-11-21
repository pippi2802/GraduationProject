#!/usr/bin/env python3
"""Lost releases over the run, frozen data (read-only). Two views, one figure per placement and period, rows = configuration, columns = utilization.
A  loss_cumulative_*: x = release index, y = cumulative lost releases (deadline miss or skipped), one line per round (4 rounds), the four rounds of full isolation
   of the same cell in grey behind. A step = an episode, a steady slope = systematic loss. y = symlog (linear up to 10), shared by all panels.
B  loss_window_*: y = lost releases in each sliding window of k = 100 releases (0..100), same layout; dotted line = worst window over the four rounds.
Release sequence per round (and first target thread where the file has a `thread` column): a job, then the releases skipped after it (skipped_before), as in
make_rq1_consecutive.py. First N_DROP = 6 jobs of every round dropped. Sources: os-experiments/analysis/data, kubedeadline-experiments/analysis/data
(full isolation, SMT, pinned tasks). n/r = not run. Writes loss_{cumulative,window}_{singlecore,multicore}_{tight,soft}.{png,svg}."""
import pathlib
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).resolve().parent
RQ1 = HERE.parent.parent
OLD, KD = RQ1 / "os-experiments" / "analysis" / "data", RQ1 / "kubedeadline-experiments" / "analysis" / "data"
N_DROP, K = 6, 100
FULL = "full isolation"
LEVERS = [("01", "isolcpus reverted"), ("02", "nohz_full reverted"), ("03", "rcu_nocbs reverted"), ("04", "systemd containment reverted"),
          ("05", "IRQ steering reverted"), ("08", "frequency pinning reverted"), ("06", "boot-params bundle reverted"), ("07", "all defaults")]
PLACE = [("single-core", "singlecore", "model1", "model1", []),
         ("multi-core", "multicore", "model5", "model5-phys", [("SMT enabled", KD / "model5-smt.csv"), ("pinned tasks", KD / "model5-phys-pinned.csv")])]
UTILS = [0.1, 0.5, 0.7, 0.94]
RCOL = {1: "#0072B2", 2: "#E69F00", 3: "#009E73", 4: "#CC79A7"}
GREY = "#b9b8b2"
COLS = ["job_index", "deadline_miss", "skipped_before", "round", "scale", "U"]


def sequences(path):
    """{(scale, U, round): 0/1 array of the release sequence}"""
    head = pd.read_csv(path, nrows=0).columns
    d = pd.read_csv(path, usecols=COLS + (["thread"] if "thread" in head else []))
    if "thread" in d.columns:
        d = d[d.thread == d.thread.min()]
    d = d[d.U.isin(UTILS) & (d.job_index >= N_DROP)].sort_values(["scale", "U", "round", "job_index"])
    out = {}
    for key, g in d.groupby(["scale", "U", "round"], sort=False):
        lost = g.deadline_miss.to_numpy(dtype=np.int8)
        extra = g.skipped_before.to_numpy(dtype=np.int64)
        seq = np.zeros(len(lost) + int(extra.sum()), dtype=np.int8)
        pos = np.arange(len(lost)) + np.r_[0, np.cumsum(extra)[:-1]]
        seq[pos] = lost
        for p, e in zip(pos, extra):
            seq[p + 1:p + 1 + e] = 1
        out[key] = seq
    return out


def window(seq):
    cs = np.r_[0, np.cumsum(seq, dtype=np.int64)]
    return cs[K:] - cs[:-K] if len(seq) >= K else np.array([int(seq.sum())])


def figure(view, slug, scale, names, seqs):
    pl_title = "Single-core" if slug == "singlecore" else "Multi-core"
    nr, nc = len(names), len(UTILS)
    fig, axes = plt.subplots(nr, nc, figsize=(11.5, 1.75 * nr + 1.0), sharex=True, sharey=True, squeeze=False)
    for i, name in enumerate(names):
        for j, u in enumerate(UTILS):
            ax = axes[i, j]
            rounds = {r: seqs[name][(scale, u, r)] for r in (1, 2, 3, 4) if (scale, u, r) in seqs[name]}
            if not rounds:
                ax.text(0.5, 0.5, "n/r", ha="center", va="center", transform=ax.transAxes, color="#52514e")
                continue
            if name != FULL:
                for r in (1, 2, 3, 4):
                    s = seqs[FULL].get((scale, u, r))
                    if s is not None:
                        ax.plot(np.cumsum(s) if view == "cumulative" else window(s), color=GREY, lw=0.7, zorder=1, rasterized=True)
            worst = 0
            for r, s in rounds.items():
                y = np.cumsum(s) if view == "cumulative" else window(s)
                ax.plot(y, color=RCOL[r], lw=0.9, zorder=2, rasterized=True, label=f"round {r}")
                worst = max(worst, int(y.max()))
            if view == "window":
                ax.axhline(worst, color="#0b0b0b", ls=":", lw=0.8, zorder=3); ax.text(0.99, 0.93, f"worst {worst}", transform=ax.transAxes, ha="right", va="top", fontsize=7)
            ax.grid(color="#e1e0d9", lw=0.4)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            ax.tick_params(labelsize=7)
        axes[i, 0].set_ylabel(name, rotation=0, ha="right", va="center", fontsize=8.5, labelpad=6)
    for j, u in enumerate(UTILS):
        axes[0, j].set_title(f"U = {u:g}", fontsize=10, fontweight="bold")
    if view == "cumulative":
        axes[0, 0].set_yscale("symlog", linthresh=10)
        axes[0, 0].set_ylim(0, None)
    else:
        axes[0, 0].set_ylim(0, 105)
    for ax in axes[-1]:
        ax.set_xlabel("release index", fontsize=8)
    h = [plt.Line2D([], [], color=RCOL[r], lw=1.6, label=f"round {r}") for r in (1, 2, 3, 4)] + [plt.Line2D([], [], color=GREY, lw=1.6, label="full isolation, same cell (4 rounds)")]
    fig.legend(handles=h, loc="upper center", ncol=5, frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, 0.975))
    ttl = ("cumulative lost releases (miss + skip), symlog y" if view == "cumulative" else f"lost releases per sliding window of k = {K}")
    fig.text(0.01, 0.998, f"{pl_title}, {ttl}, {'tight P = 10 ms' if scale == 'tight' else 'soft P = 100 ms'}", fontsize=10, fontweight="bold", va="top")
    fig.tight_layout(rect=(0.02, 0, 1, 0.945))
    for ext, kw in (("png", {"dpi": 120}), ("svg", {})):
        fig.savefig(HERE / f"loss_{view}_{slug}_{scale}.{ext}", facecolor="white", bbox_inches="tight", **kw)
    plt.close(fig)


def main():
    for pl, slug, model, fi, extra in PLACE:
        srcs = [(FULL, KD / f"{fi}.csv")] + [(n, OLD / f"{c}-{model}.csv") for c, n in LEVERS] + extra
        seqs = {n: sequences(p) for n, p in srcs}
        names = [n for n, _ in srcs]
        for scale in ("tight", "soft"):
            for view in ("cumulative", "window"):
                figure(view, slug, scale, names, seqs)
                print("done", pl, scale, view, flush=True)


main()
