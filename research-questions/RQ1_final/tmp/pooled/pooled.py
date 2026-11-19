#!/usr/bin/env python3
"""Pool the earlier campaign (4 rounds, os-experiments/analysis/data + kubedeadline-experiments full isolation) with the rerun
(os-experiments/test-results/results, 4 rounds). Read-only on the data; outputs next to this script.

Pooling: batch A (earlier) round i + batch B (rerun) round i = merged round i (4 merged rounds of ~10000 jobs per cell and thread);
the same 8 runs also pooled as one sample per cell. Columns K_reps/matrix_M (calibration constants, differ between batches) are not loaded.
Definitions as in new_experiments_runs: no job dropped (the 200 warm-up jobs are already outside the files); lost release = deadline_miss or skipped
(skipped_before); M = 100 (misses + skipped) / (jobs + skipped); S = p99.9(R)/median(R) of the pooled response times; dM = M_config - M_full isolation
(percentage points). SMT is not in the rerun and is left out. n/r = not run (U = 0.94 for isolcpus reverted / all defaults).
"""
import pathlib, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).resolve().parent
RQ1 = HERE.parent.parent
OLD = RQ1 / "os-experiments" / "analysis" / "data"
OLDFI = RQ1 / "kubedeadline-experiments" / "analysis" / "data"
NEW = RQ1 / "os-experiments" / "test-results" / "results"
FULL = "full isolation"
LEVERS = [("01", "isolcpus reverted"), ("02", "nohz_full reverted"), ("03", "rcu_nocbs reverted"), ("04", "systemd containment reverted"),
          ("05", "IRQ steering reverted"), ("08", "frequency pinning reverted"), ("06", "boot-params bundle reverted"), ("07", "all defaults")]
CONFIGS = [FULL] + [n for _, n in LEVERS]
PLACE = [("single-core", "singlecore", "model1", "model1"), ("multi-core", "multicore", "model5", "model5-phys")]
SCALES = [("tight", "Tight, $P = 10$ ms"), ("soft", "Soft, $P = 100$ ms")]
UTILS = [0.1, 0.5, 0.7, 0.94]
COLS = ["R_wall_us", "deadline_miss", "skipped_before"]


def load():
    rows = []
    for pl, _, model, fi in PLACE:
        for cfg in CONFIGS:
            code = dict((n, c) for c, n in LEVERS).get(cfg)
            old = pd.read_csv(OLDFI / f"{fi}.csv" if cfg == FULL else OLD / f"{code}-{model}.csv", usecols=COLS + ["round", "scale", "U"])
            old = old[old.U.isin(UTILS)]
            for (s, u, r), g in old.groupby(["scale", "U", "round"]):
                rows.append((pl, cfg, s, u, "A", int(r), g.R_wall_us.to_numpy(), int(g.deadline_miss.sum()), int(g.skipped_before.sum()), len(g)))
            name = fi if cfg == FULL else f"{code}-{model}"
            for r in range(1, 5):
                for s, _ in SCALES:
                    for u in UTILS:
                        p = NEW / f"{name}_round{r}" / s / f"U{u:g}" / "jobs.csv"
                        if p.is_file():
                            g = pd.read_csv(p, comment="#", usecols=COLS)
                            rows.append((pl, cfg, s, u, "B", r, g.R_wall_us.to_numpy(), int(g.deadline_miss.sum()), int(g.skipped_before.sum()), len(g)))
    return pd.DataFrame(rows, columns=["placement", "configuration", "scale", "U", "batch", "round", "R", "miss", "skip", "jobs"])


def M(d):
    return 100.0 * (d.miss.sum() + d.skip.sum()) / (d.jobs.sum() + d.skip.sum())


def S(d):
    R = np.concatenate(d.R.to_list())
    return float(np.percentile(R, 99.9) / np.median(R))


def cells(runs):
    out = []
    for (pl, cfg, s, u), g in runs.groupby(["placement", "configuration", "scale", "U"], sort=False):
        row = dict(placement=pl, configuration=cfg, scale=s, U=u, n_runs=len(g), jobs=int(g.jobs.sum()), M=M(g), S=S(g))
        for b in "AB":
            gb = g[g.batch == b]
            row[f"M_{b}"], row[f"S_{b}"] = (M(gb), S(gb)) if len(gb) else (np.nan, np.nan)
        out.append(row)
    c = pd.DataFrame(out)
    fi = c[c.configuration == FULL].set_index(["placement", "scale", "U"])
    for col in ["M", "M_A", "M_B"]:
        c["d" + col] = c[col].to_numpy() - fi[col].reindex(pd.MultiIndex.from_frame(c[["placement", "scale", "U"]])).to_numpy()
    return c


def merged_rounds(runs):
    """x/4 table: merged rounds (A_i + B_i) whose M exceeds the maximum over the merged full-isolation rounds of the cell"""
    out = []
    for (pl, cfg, s, u, r), g in runs.groupby(["placement", "configuration", "scale", "U", "round"], sort=False):
        out.append(dict(placement=pl, configuration=cfg, scale=s, U=u, round=r, M=M(g), S=S(g), jobs=int(g.jobs.sum())))
    return pd.DataFrame(out)


def fmt(x, nd):
    return "n/r" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def tex_table(c, place, col, nd, caption, label, signed=False, skip_fi=False):
    sub = c[c.placement == place]
    L = [r"\begin{table}[ht]", r"\centering", r"\small", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{l|" + "|".join(["rrrr"] * 2) + "}", r"\toprule",
         " & " + " & ".join(rf"\multicolumn{{4}}{{c}}{{{t}}}" for _, t in SCALES) + r" \\", "Configuration & " + " & ".join(f"{u:g}" for _ in SCALES for u in UTILS) + r" \\", r"\midrule"]
    for i, n in enumerate(CONFIGS):
        if i == 1:
            L.append(r"\cmidrule{1-9}")
        cs = []
        for s, _ in SCALES:
            for u in UTILS:
                r = sub[(sub.configuration == n) & (sub.scale == s) & (sub.U == u)]
                if r.empty:
                    cs.append("n/r")
                elif skip_fi and n == FULL:
                    cs.append("--")
                else:
                    v = float(r[col].iloc[0]); cs.append((f"{v:+.{nd}f}" if signed else f"{v:.{nd}f}"))
        L.append(n.replace("_", r"\_") + " & " + " & ".join(cs) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}}", r"\caption{" + caption + "}", r"\label{" + label + "}", r"\end{table}"]
    return "\n".join(L) + "\n"


def rounds_table(mr, place):
    sub = mr[mr.placement == place]
    L = [r"\begin{table}[ht]", r"\centering", r"\small", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{l|" + "|".join(["rrrr"] * 2) + "}", r"\toprule",
         " & " + " & ".join(rf"\multicolumn{{4}}{{c}}{{{t}}}" for _, t in SCALES) + r" \\", "Configuration & " + " & ".join(f"{u:g}" for _ in SCALES for u in UTILS) + r" \\", r"\midrule"]
    for i, n in enumerate(CONFIGS):
        if i == 1:
            L.append(r"\cmidrule{1-9}")
        cs = []
        for s, _ in SCALES:
            for u in UTILS:
                g = sub[(sub.configuration == n) & (sub.scale == s) & (sub.U == u)]
                f = sub[(sub.configuration == FULL) & (sub.scale == s) & (sub.U == u)]
                if g.empty:
                    cs.append("n/r")
                elif n == FULL:
                    cs.append(f"{g.M.min():.3f}--{g.M.max():.3f}")
                else:
                    cs.append(f"{int((g.M > f.M.max()).sum())}/{len(g)}")
        L.append(n.replace("_", r"\_") + " & " + " & ".join(cs) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}}", r"\caption{Merged rounds above full isolation, " + place + r". Number of the four merged rounds (earlier round $i$ plus rerun round $i$, about 10000 jobs per thread) whose miss+skip rate exceeds the maximum over the four merged full-isolation rounds of the cell; full isolation: minimum--maximum in percent. n/r: not run.}",
          r"\label{tab:rq1-pooled-rounds-" + place + "}", r"\end{table}"]
    return "\n".join(L) + "\n"


UCOL = {0.1: "#9ec5f4", 0.5: "#5598e7", 0.7: "#256abf", 0.94: "#0d366b"}
AXIS, TEXT = "#52514e", "#0b0b0b"


def figure(c, place, pslug, scale, title):
    sub = c[(c.placement == place) & (c.scale == scale)]
    multi = place == "multi-core"
    with plt.rc_context({"font.family": "sans-serif", "font.size": 10, "svg.fonttype": "path"}):
        fig, axes = plt.subplots(1, 2, figsize=(9.6, 5.2), sharey=True)
        for ax, col in zip(axes, ["S", "dM"]):
            for i, n in enumerate(CONFIGS):
                if col == "dM" and n == FULL:
                    continue
                g = sub[sub.configuration == n].sort_values("U")
                if g.empty:
                    continue
                x = g[col].to_numpy(float)
                ax.plot([x.min(), x.max()], [i, i], color="#cfcfcf", lw=1.0, zorder=2)
                for u, xv in zip(g.U, x):
                    ax.plot(xv, i, "o", ms=8, mfc=UCOL[u], mec="white", mew=1.5, zorder=3)
                j = int(np.argmax(x)); xm = x[j]
                if (col == "S" and xm >= 1.5) or (col == "dM" and xm >= 0.25):
                    lab = f"{xm:.1f}" if col == "S" else f"{xm:+.1f}"
                    ax.annotate(lab, (xm, i), xytext=(-7 if col == "S" else 7, 0), textcoords="offset points", ha="right" if col == "S" else "left", va="center", fontsize=8.5, color=TEXT)
            ax.axvline(1 if col == "S" else 0, color=AXIS, ls="--", lw=0.8)
            ax.grid(axis="x", color="#e1e0d9", lw=0.6); ax.set_axisbelow(True)
            for sp in ["top", "right"]:
                ax.spines[sp].set_visible(False)
        axes[0].set_xscale("log"); axes[0].set_xlim(0.9, 70)
        axes[0].set_xlabel("tail spread $S = p_{99.9}(R)/\\mathrm{median}(R)$ (log)")
        if multi:
            axes[1].set_xscale("symlog", linthresh=1.0, linscale=1.0); axes[1].set_xlim(-0.5, 900); axes[1].set_xticks([0, 1, 5, 20, 100]); axes[1].set_xticklabels(["0", "1", "5", "20", "100"])
            axes[1].set_xlabel("change in miss rate from\nfull isolation [percentage points]\n(symlog axis)")
        else:
            axes[1].set_xlim(-0.5, 6); axes[1].set_xticks(range(0, 7))
            axes[1].set_xlabel("change in miss rate from\nfull isolation [percentage points]")
        axes[0].set_yticks(range(len(CONFIGS))); axes[0].set_yticklabels(CONFIGS); axes[0].invert_yaxis()
        axes[0].axhline(0.5, color=AXIS, lw=0.8)
        from matplotlib.lines import Line2D
        fig.legend([Line2D([], [], marker="o", ls="", color=UCOL[u], mec="white") for u in UTILS], [f"U = {u:g}" for u in UTILS], loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.01))
        fig.suptitle(f"{'Single' if not multi else 'Multi'}-core, {title} (8 runs pooled per cell)", fontsize=11, x=0.02, ha="left")
        fig.subplots_adjust(left=0.27, right=0.98, top=0.92, bottom=0.2, wspace=0.12)
        for ext, kw in (("svg", {}), ("png", {"dpi": 200})):
            fig.savefig(HERE / f"rq1_{pslug}_{scale}.{ext}", facecolor="white", **kw)
        plt.close(fig)


if __name__ == "__main__":
    runs = load()
    c = cells(runs)
    c.to_csv(HERE / "pooled_cells.csv", index=False)
    mr = merged_rounds(runs)
    mr.to_csv(HERE / "pooled_merged_rounds.csv", index=False)
    for pl, ps, *_ in PLACE:
        (HERE / f"table_spread_{pl}.tex").write_text(tex_table(c, pl, "S", 2, f"Tail spread $S = p_{{99.9}}(R)/\\mathrm{{median}}(R)$, {pl}, all eight runs of a cell pooled (earlier campaign and rerun, four rounds each). n/r: not run.", f"tab:rq1-pooled-spread-{pl}"))
        (HERE / f"table_increase_{pl}.tex").write_text(tex_table(c, pl, "dM", 3, f"Increase of the miss+skip rate over full isolation (percentage points), {pl}, all eight runs of a cell pooled: $M_{{config}} - M_{{FI}}$ with $M = 100\\,(\\mathrm{{misses}}+\\mathrm{{skipped}})/(\\mathrm{{jobs}}+\\mathrm{{skipped}})$. n/r: not run.", f"tab:rq1-pooled-increase-{pl}", signed=True, skip_fi=True))
        (HERE / f"table_rounds_{pl}.tex").write_text(rounds_table(mr, pl))
        for s, t in SCALES:
            figure(c, pl, ps, s, t)
    pd.set_option("display.width", 250)
    for pl, *_ in PLACE:
        print(pl); print(c[c.placement == pl].pivot_table(index="configuration", columns=["scale", "U"], values="S").reindex(CONFIGS).round(2).to_string())
        print(c[c.placement == pl].pivot_table(index="configuration", columns=["scale", "U"], values="dM").reindex(CONFIGS).round(2).to_string())
