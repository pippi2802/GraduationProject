#!/usr/bin/env python3
"""Final tables and figures of RQ1 (OS-level isolation experiments): two tables and two heatmaps, single-core and multi-core.

    python3 make_results_final.py

Writes, next to this script (nothing else):
  table_single-core.csv/.tex     table_multi-core.csv/.tex
  spread_single-core.csv/.tex/.png/.svg     spread_multi-core.csv/.tex/.png/.svg     (relative spread against utilization, one panel per period)
  heatmap_single-core.csv/.tex/.png/.svg     heatmap_multi-core.csv/.tex/.png/.svg

Data: ../analysis/data/<scenario>-<model>.csv (one file per removed lever; model1 = single-core, model5 = multi-core on physical cores) and the
full-isolation runs ../../kubedeadline-experiments/analysis/data/{model1,model5-phys}.csv. One row per executed job; the releases that were
skipped after an overrun have no row, they are counted by the column skipped_before of the job that caused them (see workload.c).

Start-up: the first N_DROP = 6 jobs after every restart (the start of a round) are dropped, with the releases skipped after them, from every statistic; the jobs that
remain of a cell are one continuous sequence (no per-round statistics). The version with the warm-up included is not kept here.
Definitions (D = T, the period of the scale; every number pools the rounds of a cell):
  Miss rate [%]     lost releases / releases = (jobs with R > D + skipped) / (jobs + skipped), in percent
  Tail spread       p99.9 / median of the response time R of the executed jobs
  Relative spread   tail spread of the configuration / tail spread of full isolation (same scale and utilization); 1 = as good as full isolation.
                    Not in the tables (it is in their CSV); it is the y-axis of the spread figures
  Heatmap cell      m = number of releases that were not lost (met their deadline and were not skipped) in the worst window of k = 100 consecutive releases;
                    the window runs over the release sequence of the whole cell, a skipped release sits right after the job that caused it
A cell that was not run (no data) is written -- in the tables and hatched in the heatmaps.
Needs numpy, pandas, matplotlib.
"""
import pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines
import matplotlib.patches
from matplotlib.colors import LinearSegmentedColormap

HERE = pathlib.Path(__file__).resolve().parent
OS_DATA = HERE.parent / "analysis" / "data"
BASE_DATA = HERE.parent.parent / "kubedeadline-experiments" / "analysis" / "data"

FULL = "full isolation"
SCENARIOS = [("01", "isolcpus removed"), ("02", "nohz_full removed"), ("03", "rcu_nocbs removed"), ("04", "systemd containment removed"),
             ("05", "IRQ steering removed"), ("06", "boot-params bundle removed"), ("08", "frequency pinning removed")]
SMT = "SMT enabled"                                                                              # multi-core only: full isolation with SMT switched on
CONFIGS = [FULL] + [name for _, name in SCENARIOS]
CONFIGS_OF = {"single-core": CONFIGS, "multi-core": CONFIGS + [SMT]}
PLACEMENTS = [("single-core", "model1", "model1"), ("multi-core", "model5", "model5-phys")]      # label, model of the lever runs, file of the full-isolation runs
SMT_FILE = "model5-smt"
SCALES = [("tight", "Tight, $P = 10$ ms", 10_000), ("soft", "Soft, $P = 100$ ms", 100_000)]       # column groups, left to right
UTILS = [0.1, 0.5, 0.7, 0.94]
K = 100
N_DROP = 6              # jobs dropped after every restart (start-up transient, see the warm-up analysis); the remaining jobs of a cell are one continuous sequence


def read(path):
    df = pd.read_csv(path, usecols=["job_index", "R_wall_us", "deadline_miss", "skipped_before", "round", "scale", "U"])
    return df.sort_values(["round", "job_index"]).reset_index(drop=True)


def load(label, model, base_file):
    """{(configuration, scale, U): dataframe of the cell}; the first N_DROP jobs after every restart (round) are dropped, with the releases skipped after them"""
    cells = {}
    sources = [(FULL, BASE_DATA / f"{base_file}.csv")] + [(name, OS_DATA / f"{code}-{model}.csv") for code, name in SCENARIOS]
    if label == "multi-core":
        sources.append((SMT, BASE_DATA / f"{SMT_FILE}.csv"))
    for name, path in sources:
        df = read(path)
        for (scale, u), g in df.groupby(["scale", "U"]):
            if u in UTILS:
                cells[(name, scale, u)] = g[g.job_index >= N_DROP].reset_index(drop=True)
    return cells


def worst_lost_window(g, k=K):
    """most lost releases (R > D or skipped) in any window of k consecutive releases of the cell: the retained rounds form one continuous release sequence"""
    seqs = []
    for _, rg in g.groupby("round", sort=False):
        lost = rg.deadline_miss.to_numpy(dtype=int)
        extra = rg.skipped_before.to_numpy(dtype=int)
        seq = np.zeros(len(lost) + extra.sum(), dtype=np.int8)                   # release sequence: a job, then the releases skipped after it
        pos = np.arange(len(lost)) + np.r_[0, np.cumsum(extra)[:-1]]
        seq[pos] = lost
        for p, e in zip(pos, extra):
            seq[p + 1:p + 1 + e] = 1
        seqs.append(seq)
    seq = np.concatenate(seqs)
    cs = np.r_[0, np.cumsum(seq)]
    return int((cs[k:] - cs[:-k]).max())


START_JOBS, START_SHARE = 5, 0.25   # a cell is start-up dominated when at least a quarter of its jobs above the p99.9 are among the first 5 retained jobs of a round


def startup_share(g):
    """share of the jobs above the p99.9 of the cell that are among the first START_JOBS jobs of their round (the start-up transient of a round)"""
    r = g.R_wall_us.to_numpy()
    above = r > np.percentile(r, 99.9)
    return float((above & (g.job_index.to_numpy() < N_DROP + START_JOBS)).sum() / above.sum()) if above.any() else 0.0


def cell_numbers(g):
    n, skipped, misses = len(g), int(g.skipped_before.sum()), int(g.deadline_miss.sum())
    r = g.R_wall_us.to_numpy()
    return dict(jobs=n, skipped=skipped, misses=misses, miss_rate_pct=100 * (misses + skipped) / (n + skipped),
                tail_spread=float(np.percentile(r, 99.9) / np.median(r)), startup_share=startup_share(g), max_lost_k100=worst_lost_window(g))


def collect(label, cells):
    rows = []
    for config in CONFIGS_OF[label]:
        for scale, _, _ in SCALES:
            for u in UTILS:
                g = cells.get((config, scale, u))
                rows.append(dict(placement=label, configuration=config, scale=scale, U=u, **(cell_numbers(g) if g is not None else {})))
    t = pd.DataFrame(rows)
    full = t[t.configuration == FULL].set_index(["scale", "U"]).tail_spread
    t["relative_spread"] = [ts / full[(s, u)] for ts, s, u in zip(t.tail_spread, t.scale, t.U)]
    t["m"] = K - t.max_lost_k100
    t["status"] = np.where(t.jobs.isna(), "not run", "measured")
    return t


# ---------------------------------------------------------------- tables
def tex_name(s):
    return s.replace("_", r"\_")


def fmt_rate(x):
    return "--" if pd.isna(x) else f"{x:.3f}"


def fmt_ratio(x):
    return "--" if pd.isna(x) else f"{x:.2f}"


def table_tex(t, label):
    ncol = len(SCALES) * len(UTILS)
    lines = [r"\begin{table}[ht]", r"\centering", r"\small", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{ll|" + "|".join(["r" * len(UTILS)] * len(SCALES)) + "}", r"\toprule",
             " &  & " + " & ".join(rf"\multicolumn{{{len(UTILS)}}}{{c}}{{{title}}}" for _, title, _ in SCALES) + r" \\",
             "Configuration & Metric & " + " & ".join(f"{u:g}" for _ in SCALES for u in UTILS) + r" \\", r"\midrule"]
    metrics = [("miss_rate_pct", "Miss rate [\\%]", fmt_rate), ("tail_spread", "Tail spread", fmt_ratio)]
    for i, config in enumerate(CONFIGS_OF[label]):
        if i:
            lines.append(rf"\cmidrule{{1-{2 + ncol}}}")
        sub = t[t.configuration == config]
        for j, (col, name, f) in enumerate(metrics):
            vals = [sub[(sub.scale == s) & (sub.U == u)].iloc[0][col] for s, _, _ in SCALES for u in UTILS]
            first = rf"\multirow[t]{{2}}{{*}}{{{tex_name(config)}}}" if j == 0 else ""
            lines.append(f"{first} & {name} & " + " & ".join(f(v) for v in vals) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}}",
              r"\caption{Isolation levers, " + label + r". Miss rate: share of releases lost, that is jobs with $R>P$ plus releases skipped after an overrun, over all releases of the cell. "
              r"Tail spread: $p_{99.9}/\mathrm{median}$ of the response time of the executed jobs. The first six jobs after every restart are excluded. Cells marked -- were not run.}",
              r"\label{tab:rq1-" + label + r"}", r"\end{table}"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- heatmaps
RED_BLACK = LinearSegmentedColormap.from_list("red_to_black", [(0.0, "#ffffff"), (0.04, "#fee0d2"), (0.30, "#fb6a4a"), (0.60, "#cb181d"), (0.85, "#67000d"), (1.0, "#000000")])
HM_COLS = [(s, u) for s, _, _ in SCALES for u in UTILS]


def heatmap(t, label, stem):
    tab = t.set_index(["configuration", "scale", "U"])
    cell_w, row_h, gap, label_w = 1.0, 1.0, 0.55, 4.6
    xs = {c: i + (gap if i >= len(UTILS) else 0) for i, c in enumerate(HM_COLS)}
    configs = CONFIGS_OF[label]
    ypos = {c: 2.4 + i * row_h for i, c in enumerate(configs)}
    total_h = 2.4 + len(configs) * row_h + 0.2
    width_in = 12.5 / 2.54
    unit_in = width_in / (label_w + len(HM_COLS) + gap + 0.2)
    height_in = total_h * unit_in * 0.62 + 0.75
    with plt.rc_context({"font.size": 7, "font.family": "serif", "svg.fonttype": "path"}):
        fig = plt.figure(figsize=(width_in, height_in))
        ax = fig.add_axes([0.0, 0.75 / height_in, 1.0, 1 - 0.75 / height_in])
        ax.set_xlim(-label_w, len(HM_COLS) + gap + 0.2); ax.set_ylim(total_h, 0); ax.axis("off")
        ax.text(-label_w + 0.1, 0.55, label, ha="left", va="center", fontsize=8, fontweight="bold")
        for scale, title, _ in SCALES:
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
                r = tab.loc[(config, c[0], c[1])]
                x0 = xs[c]
                if r.status == "not run":
                    ax.add_patch(plt.Rectangle((x0, yy), cell_w, row_h, facecolor="white", edgecolor="#aaaaaa", linewidth=0.5, hatch="////", zorder=1))
                    ax.text(x0 + cell_w / 2, yy + row_h / 2, "not run", ha="center", va="center", fontsize=4.2, color="#555555", zorder=3,
                            bbox=dict(facecolor="white", edgecolor="none", pad=0.4))
                    continue
                rgba = RED_BLACK(np.sqrt(r.max_lost_k100 / K))
                lum = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                ax.add_patch(plt.Rectangle((x0, yy), cell_w, row_h, facecolor=rgba, edgecolor="#d9d9d9", linewidth=0.5))
                ax.text(x0 + cell_w / 2, yy + row_h / 2, f"{int(r.m)}", ha="center", va="center", fontsize=6.0, color="white" if lum < 0.45 else "#1a1a1a")
        cax = fig.add_axes([0.30, 0.46 / height_in, 0.66, 0.13 / height_in])
        cax.imshow(np.linspace(0, 1, 512)[None, :], aspect="auto", cmap=RED_BLACK, extent=[0, 1, 0, 1])
        ticks = [0, 0.10, 0.25, 0.50, 0.75, 1.0]
        cax.set_xticks(np.sqrt(ticks)); cax.set_xticklabels([f"{int(x * 100)}%" for x in ticks], fontsize=7)
        cax.set_yticks([])
        cax.set_xlabel("Loss in worst window (share of $k = 100$ releases lost)", fontsize=7.5, labelpad=2)
        for s in cax.spines.values():
            s.set_linewidth(0.5)
        fig.savefig(HERE / f"{stem}.png", dpi=300)
        fig.savefig(HERE / f"{stem}.svg")
    plt.close(fig)
    (HERE / f"{stem}.tex").write_text("\n".join([
        r"\begin{figure}[ht]", r"\centering", r"\includegraphics[width=\textwidth]{" + stem + ".png}",
        r"\caption{Worst window of $k = 100$ consecutive releases for every configuration, period and utilization, " + label + r". Each cell gives $m$, the smallest number of releases "
        r"that met their deadline and were not skipped in any window of 100 releases. Cells with $m = 100$ have no colour; the more releases lost, the more intense the red, and black means "
        r"that every release of the window was lost. The colour follows the loss $(k-m)/k$ on a \emph{square-root} scale, so that small losses stay distinguishable from zero. The first six jobs after every restart are excluded. Hatched cells were not run.}",
        r"\label{fig:rq1-" + stem.replace("_", "-") + "}", r"\end{figure}"]) + "\n")


# ---------------------------------------------------------------- relative spread against utilization
LINES = {"isolcpus removed": "#0072B2", "nohz_full removed": "#D55E00", "systemd containment removed": "#009E73", "rcu_nocbs removed": "#CC79A7"}
LINE_MARK = {"isolcpus removed": "o", "nohz_full removed": "s", "systemd containment removed": "^", "rcu_nocbs removed": "D"}
# SMT is not drawn: it shifts the whole distribution (the median moves to about P), so the tail-to-median ratio cannot show its effect (see the miss-rate table and the heatmap)
OTHER = ["IRQ steering removed", "boot-params bundle removed", "frequency pinning removed"]          # drawn as one min-max band
OTHER_NAME = "IRQ steering, boot-params, frequency pinning removed (min-max)"
# hollow cell: start-up dominated (startup_share >= START_SHARE) in the configuration or in full isolation (the reference); left out of the band, not joined by a line


def spread_figure(t, label, stem):
    single = t.set_index(["configuration", "scale", "U"]).startup_share.ge(START_SHARE)
    burst = lambda lab, scale, u, c: bool(single.get((c, scale, u), False) or single.get((FULL, scale, u), False))
    rs = t.set_index(["configuration", "scale", "U"]).relative_spread
    x = np.arange(len(UTILS))
    lines = [c for c in LINES if c in CONFIGS_OF[label]]
    with plt.rc_context({"font.size": 7, "font.family": "serif", "svg.fonttype": "path"}):
        fig, axes = plt.subplots(1, 2, figsize=(12.5 / 2.54, 5.4 / 2.54 + 0.9), sharey=True)
        for ax, (scale, title, _) in zip(axes, SCALES):
            get = lambda c: np.array([rs.get((c, scale, u), np.nan) for u in UTILS], dtype=float)
            band = np.array([[get(c)[i] if not burst(label, scale, u, c) else np.nan for c in OTHER] for i, u in enumerate(UTILS)])
            lo, hi = np.min(np.where(np.isnan(band), np.inf, band), axis=1), np.max(np.where(np.isnan(band), -np.inf, band), axis=1)
            ok = np.isfinite(lo) & np.isfinite(hi)
            ax.fill_between(x, np.where(ok, lo, np.nan), np.where(ok, hi, np.nan), color="#bdbdbd", alpha=0.55, lw=0, zorder=1)
            for c in OTHER:                                                       # the cells left out of the band, as hollow grey points
                for i, u in enumerate(UTILS):
                    if burst(label, scale, u, c) and not np.isnan(get(c)[i]):
                        ax.scatter(x[i], get(c)[i], s=14, facecolor="white", edgecolor="#7f7f7f", lw=0.8, zorder=3)
            ax.axhline(1, color="#555555", lw=0.8, ls=(0, (4, 2)), zorder=2)
            for c in lines:
                y = get(c)
                hol = np.array([burst(label, scale, u, c) for u in UTILS])
                yl = np.where(hol, np.nan, y)                                        # the line is broken at hollow points
                ax.plot(x, yl, color=LINES[c], lw=1.2, zorder=4)
                for i, u in enumerate(UTILS):
                    if not np.isnan(y[i]):
                        ax.scatter(x[i], y[i], s=16, marker=LINE_MARK[c], facecolor="white" if burst(label, scale, u, c) else LINES[c], edgecolor=LINES[c], lw=1.0, zorder=5)
            ax.set_yscale("log")
            ax.set_xticks(x); ax.set_xticklabels([f"{u:g}" for u in UTILS])
            ax.set_xlim(-0.3, len(UTILS) - 0.7)
            ax.set_xlabel("Utilization $U$")
            ax.set_title(title, fontsize=8, fontweight="bold")
            ax.grid(axis="y", color="#e0e0e0", lw=0.5, zorder=0)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
        axes[0].set_ylabel("Relative spread (log scale)")
        axes[0].set_yticks([0.2, 0.5, 1, 2, 5, 10]); axes[0].set_yticklabels(["0.2", "0.5", "1", "2", "5", "10"])
        axes[0].minorticks_off()
        handles = [matplotlib.lines.Line2D([], [], color=LINES[c], marker=LINE_MARK[c], ms=4, lw=1.2, label=c) for c in lines]
        handles.append(matplotlib.patches.Patch(facecolor="#bdbdbd", alpha=0.55, label=OTHER_NAME))
        handles.append(matplotlib.lines.Line2D([], [], color="#555555", lw=0.8, ls=(0, (4, 2)), label="full isolation (= 1)"))
        if single.any():
            handles.append(matplotlib.lines.Line2D([], [], color="#7f7f7f", marker="o", mfc="white", lw=0, ms=4, label="hollow: p99.9 set by round start-up (excluded from the band)"))
        fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False, fontsize=6.3, handlelength=1.6, columnspacing=1.4, bbox_to_anchor=(0.5, 0.0))
        fig.subplots_adjust(left=0.10, right=0.99, top=0.91, bottom=0.40 if len(lines) > 4 else 0.37, wspace=0.08)
        fig.savefig(HERE / f"{stem}.png", dpi=300)
        fig.savefig(HERE / f"{stem}.svg")
    plt.close(fig)
    t.assign(group=np.where(t.configuration.isin(OTHER), "other settings (band)", np.where(t.configuration.isin(lines), "own line", "reference")),
             single_burst=[burst(label, s_, u, c) for c, s_, u in zip(t.configuration, t.scale, t.U)])[
        ["placement", "configuration", "scale", "U", "tail_spread", "relative_spread", "startup_share", "group", "single_burst"]].to_csv(HERE / f"{stem}.csv", index=False)
    (HERE / f"{stem}.tex").write_text("\n".join([
        r"\begin{figure}[ht]", r"\centering", r"\includegraphics[width=\textwidth]{" + stem + ".png}",
        r"\caption{Relative spread against utilization, " + label + r": tail spread ($p_{99.9}/\mathrm{median}$ of the response time) of the configuration divided by that of full isolation "
        r"(dashed line, 1), for the 10\,ms (left) and 100\,ms (right) period. Each line is one removed setting" + "" + r"; the grey band spans the minimum and "
        r"maximum of IRQ steering, the boot-params bundle and frequency pinning. " + (r"Hollow points are cells whose $p_{99.9}$ is dominated by the start-up of the rounds: at least a quarter of the jobs above it are among the first five retained jobs of a round, "
        r"in the configuration or in full isolation (the reference); they are left out of the band and not joined by a line. " if single.any() else "") +
        r"The first six jobs after every restart are excluded. The vertical axis is logarithmic. SMT enabled is not drawn: it shifts the whole distribution, "
        r"including the median, so a tail-to-median ratio cannot show its effect (see Table~\ref{tab:rq1-multi-core} and the heatmap).}", r"\label{fig:rq1-" + stem.replace("_", "-") + "}", r"\end{figure}"]) + "\n")


# ---------------------------------------------------------------- main
for label, model, base_file in PLACEMENTS:
    t = collect(label, load(label, model, base_file))
    t[["placement", "configuration", "scale", "U", "jobs", "skipped", "misses", "miss_rate_pct", "tail_spread", "relative_spread"]].to_csv(HERE / f"table_{label}.csv", index=False)
    (HERE / f"table_{label}.tex").write_text(table_tex(t, label))
    t[["placement", "configuration", "scale", "U", "max_lost_k100", "m", "status"]].assign(k=K, loss_fraction=lambda d: d.max_lost_k100 / K).to_csv(HERE / f"heatmap_{label}.csv", index=False)
    heatmap(t, label, f"heatmap_{label}")
    spread_figure(t, label, f"spread_{label}")
    ran = t[t.status == "measured"]
    print(f"{label}: {len(ran)} cells measured, {int((t.status == 'not run').sum())} not run; miss rate {ran.miss_rate_pct.min():.3f}-{ran.miss_rate_pct.max():.3f}%, "
          f"relative spread {ran.relative_spread.min():.2f}-{ran.relative_spread.max():.2f}, worst window m {int(ran.m.min())}-{int(ran.m.max())}")
