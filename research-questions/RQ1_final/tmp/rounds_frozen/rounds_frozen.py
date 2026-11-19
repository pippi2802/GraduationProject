#!/usr/bin/env python3
"""Rounds above full isolation, frozen RQ1_final data only (os-experiments/analysis/data + kubedeadline-experiments full isolation / SMT).
For every cell: number of rounds whose miss+skip rate M = 100 (misses+skipped)/(jobs+skipped) is strictly larger than the maximum over the
full-isolation rounds of the cell (first N_DROP = 6 jobs of every round dropped, as in make_results_final.py; threads of a round pooled).
Full isolation row: min--max of its rounds in percent. Writes rounds_{single,multi}-core.{tex,csv,png,svg}."""
import pathlib
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).resolve().parent
RQ1 = HERE.parent.parent
OLD = RQ1 / "os-experiments" / "analysis" / "data"
KD = RQ1 / "kubedeadline-experiments" / "analysis" / "data"
N_DROP = 6
FULL = "full isolation"
LEVERS = [("01", "isolcpus reverted"), ("02", "nohz_full reverted"), ("03", "rcu_nocbs reverted"), ("04", "systemd containment reverted"),
          ("05", "IRQ steering reverted"), ("08", "frequency pinning reverted"), ("06", "boot-params bundle reverted"), ("07", "all defaults")]
PLACE = [("single-core", "model1", "model1", []), ("multi-core", "model5", "model5-phys", [("SMT enabled", KD / "model5-smt.csv")])]
SCALES = [("tight", "Tight, $P = 10$ ms"), ("soft", "Soft, $P = 100$ ms")]
UTILS = [0.1, 0.5, 0.7, 0.94]
COLS = ["job_index", "deadline_miss", "skipped_before", "round", "scale", "U"]


def per_round(path):
    d = pd.read_csv(path, usecols=COLS)
    d = d[d.U.isin(UTILS) & (d.job_index >= N_DROP)]
    g = d.groupby(["scale", "U", "round"]).agg(miss=("deadline_miss", "sum"), skip=("skipped_before", "sum"), jobs=("job_index", "size")).reset_index()
    g["M"] = 100.0 * (g.miss + g.skip) / (g.jobs + g.skip)
    return g


def main():
    for pl, model, fi, extra in PLACE:
        srcs = [(FULL, KD / f"{fi}.csv")] + [(n, OLD / f"{c}-{model}.csv") for c, n in LEVERS] + extra
        names = [n for n, _ in srcs]
        runs = {n: per_round(p) for n, p in srcs}
        rows, cell = [], {}
        for n in names:
            for s, _ in SCALES:
                for u in UTILS:
                    g = runs[n][(runs[n].scale == s) & (runs[n].U == u)]
                    f = runs[FULL][(runs[FULL].scale == s) & (runs[FULL].U == u)]
                    if g.empty:
                        cell[(n, s, u)] = None; continue
                    if n == FULL:
                        cell[(n, s, u)] = (g.M.min(), g.M.max(), len(g)); rows.append((pl, n, s, u, len(g), g.M.min(), g.M.max(), np.nan))
                    else:
                        k = int((g.M > f.M.max()).sum()); cell[(n, s, u)] = (k, len(g)); rows.append((pl, n, s, u, len(g), g.M.min(), g.M.max(), k))
        pd.DataFrame(rows, columns=["placement", "configuration", "scale", "U", "n_rounds", "M_min", "M_max", "rounds_above_FI_max"]).to_csv(HERE / f"rounds_{pl}.csv", index=False)
        # tex
        L = [r"\begin{table}[ht]", r"\centering", r"\small", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{l|rrrr|rrrr}", r"\toprule",
             " & " + " & ".join(rf"\multicolumn{{4}}{{c}}{{{t}}}" for _, t in SCALES) + r" \\", "Configuration & " + " & ".join(f"{u:g}" for _ in SCALES for u in UTILS) + r" \\", r"\midrule"]
        for i, n in enumerate(names):
            if i == 1:
                L.append(r"\cmidrule{1-9}")
            cs = []
            for s, _ in SCALES:
                for u in UTILS:
                    v = cell[(n, s, u)]
                    cs.append("n/r" if v is None else (f"{v[0]:.3f}--{v[1]:.3f}" if n == FULL else f"{v[0]}/{v[1]}"))
            L.append(n.replace("_", r"\_") + " & " + " & ".join(cs) + r" \\")
        L += [r"\bottomrule", r"\end{tabular}}", r"\caption{Rounds above full isolation, " + pl + r" (frozen data). Number of rounds whose miss+skip rate (lost releases over all releases, in percent) exceeds the maximum over the full-isolation rounds of the cell; full isolation: minimum--maximum in percent. n/r: not run.}",
              r"\label{tab:rq1-frozen-rounds-" + pl + "}", r"\end{table}"]
        (HERE / f"rounds_{pl}.tex").write_text("\n".join(L) + "\n")
        # figure: grid of fractions
        cols = [(s, u) for s, _ in SCALES for u in UTILS]
        val = np.full((len(names), len(cols)), np.nan)
        for i, n in enumerate(names):
            for j, (s, u) in enumerate(cols):
                v = cell[(n, s, u)]
                if v is not None and n != FULL:
                    val[i, j] = v[0] / v[1]
        fig, ax = plt.subplots(figsize=(9.5, 0.45 * len(names) + 1.6))
        cm = plt.get_cmap("Blues").copy(); cm.set_bad("#f0efe9")
        ax.imshow(np.ma.masked_invalid(val), cmap=cm, vmin=0, vmax=1.2, aspect="auto")
        for i, n in enumerate(names):
            for j, (s, u) in enumerate(cols):
                v = cell[(n, s, u)]
                if v is None:
                    t, col = "n/r", "#52514e"
                elif n == FULL:
                    t, col = f"{v[0]:.2f}–{v[1]:.2f}", "#0b0b0b"
                else:
                    t, col = f"{v[0]}/{v[1]}", "white" if v[0] / v[1] > 0.6 else "#0b0b0b"
                ax.text(j, i, t, ha="center", va="center", fontsize=9 if n == FULL else 10.5, color=col, fontweight="bold" if (n != FULL and v and v[0] > 0) else "normal")
        ax.set_xticks(range(len(cols))); ax.set_xticklabels([f"{u:g}" for _, u in cols]); ax.set_yticks(range(len(names))); ax.set_yticklabels(names)
        ax.set_xlabel("Utilization $U$"); ax.axvline(3.5, color="white", lw=6); ax.axhline(0.5, color="#52514e", lw=1.2)
        for q, (s, t) in enumerate(SCALES):
            ax.text(q * 4 + 1.5, -0.75, t, ha="center", va="bottom", fontsize=11, fontweight="bold")
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.tick_params(length=0)
        fig.text(0.01, 0.01, "Number of rounds with miss+skip rate above the maximum of the full-isolation rounds of the cell (x/n). Full isolation: min–max of its rounds in %. n/r: not run.", fontsize=8, color="#52514e")
        fig.subplots_adjust(left=0.27, right=0.99, top=0.9, bottom=0.17)
        for ext, kw in (("svg", {}), ("png", {"dpi": 200})):
            fig.savefig(HERE / f"rounds_{pl}.{ext}", facecolor="white", **kw)
        plt.close(fig)
        print(pl); print("\n".join(L[9:9 + len(names) + 1]))


main()
