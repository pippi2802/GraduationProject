#!/usr/bin/env python3
"""Execution-time (C = C_cputime_us) counterpart of the response-time tables of results_final: same cells, same layout, same N_DROP = 6.

    python3 make_exec_time_table.py

Writes next to this script: exec_table_single-core.csv/.tex, exec_table_multi-core.csv/.tex
Rows per configuration: median C [ms] and tail spread p99.9/median of C (relative spread to full isolation is in the CSV).
"""
import pathlib
import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
OS_DATA = HERE.parent.parent / "os-experiments" / "analysis" / "data"
BASE_DATA = HERE.parent.parent / "kubedeadline-experiments" / "analysis" / "data"

FULL, SMT = "full isolation", "SMT enabled"
SCENARIOS = [("01", "isolcpus removed"), ("02", "nohz_full removed"), ("03", "rcu_nocbs removed"), ("04", "systemd containment removed"),
             ("05", "IRQ steering removed"), ("06", "boot-params bundle removed"), ("08", "frequency pinning removed")]
CONFIGS = [FULL] + [n for _, n in SCENARIOS]
CONFIGS_OF = {"single-core": CONFIGS, "multi-core": CONFIGS + [SMT]}
PLACEMENTS = [("single-core", "model1", "model1"), ("multi-core", "model5", "model5-phys")]
SCALES = [("tight", "Tight, $P = 10$ ms"), ("soft", "Soft, $P = 100$ ms")]
UTILS = [0.1, 0.5, 0.7, 0.94]
N_DROP = 6


def load(label, model, base_file):
    cells = {}
    sources = [(FULL, BASE_DATA / f"{base_file}.csv")] + [(n, OS_DATA / f"{c}-{model}.csv") for c, n in SCENARIOS]
    if label == "multi-core":
        sources.append((SMT, BASE_DATA / "model5-smt.csv"))
    for name, path in sources:
        df = pd.read_csv(path, usecols=["job_index", "C_cputime_us", "scale", "U"])
        for (scale, u), g in df.groupby(["scale", "U"]):
            if u in UTILS:
                cells[(name, scale, u)] = g[g.job_index >= N_DROP].C_cputime_us.to_numpy()
    return cells


def collect(label, cells):
    rows = []
    for config in CONFIGS_OF[label]:
        for scale, _ in SCALES:
            for u in UTILS:
                c = cells.get((config, scale, u))
                rows.append(dict(placement=label, configuration=config, scale=scale, U=u,
                                 **({} if c is None else dict(jobs=len(c), median_C_ms=np.median(c) / 1000, p999_C_ms=np.percentile(c, 99.9) / 1000,
                                                              tail_spread=np.percentile(c, 99.9) / np.median(c)))))
    t = pd.DataFrame(rows)
    full = t[t.configuration == FULL].set_index(["scale", "U"]).tail_spread
    t["relative_spread"] = [ts / full[(s, u)] for ts, s, u in zip(t.tail_spread, t.scale, t.U)]
    return t


def f(x, nd):
    return "--" if pd.isna(x) else f"{x:.{nd}f}"


def table_tex(t, label):
    ncol = len(SCALES) * len(UTILS)
    lines = [r"\begin{table}[ht]", r"\centering", r"\small", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{ll|" + "|".join(["r" * len(UTILS)] * len(SCALES)) + "}", r"\toprule",
             " &  & " + " & ".join(rf"\multicolumn{{{len(UTILS)}}}{{c}}{{{title}}}" for _, title in SCALES) + r" \\",
             "Configuration & Metric & " + " & ".join(f"{u:g}" for _ in SCALES for u in UTILS) + r" \\", r"\midrule"]
    metrics = [("median_C_ms", "Median $C$ [ms]", 2), ("tail_spread", "Tail spread", 2)]
    for i, config in enumerate(CONFIGS_OF[label]):
        if i:
            lines.append(rf"\cmidrule{{1-{2 + ncol}}}")
        sub = t[t.configuration == config]
        for j, (col, name, nd) in enumerate(metrics):
            vals = [sub[(sub.scale == s) & (sub.U == u)].iloc[0][col] for s, _ in SCALES for u in UTILS]
            first = rf"\multirow[t]{{2}}{{*}}{{{config.replace('_', chr(92) + '_')}}}" if j == 0 else ""
            lines.append(f"{first} & {name} & " + " & ".join(f(v, nd) for v in vals) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}}",
              r"\caption{Execution time of the jobs under the isolation levers, " + label + r". Median $C$: median CPU time of a job. Tail spread: $p_{99.9}/\mathrm{median}$ of $C$. "
              r"The first six jobs after every restart are excluded. Cells marked -- were not run.}", r"\label{tab:rq1-exec-" + label + r"}", r"\end{table}"]
    return "\n".join(lines) + "\n"


for label, model, base_file in PLACEMENTS:
    t = collect(label, load(label, model, base_file))
    t.to_csv(HERE / f"exec_table_{label}.csv", index=False)
    (HERE / f"exec_table_{label}.tex").write_text(table_tex(t, label))
    r = t.dropna(subset=["jobs"])
    print(label, f"median C {r.median_C_ms.min():.2f}-{r.median_C_ms.max():.2f} ms, tail spread {r.tail_spread.min():.2f}-{r.tail_spread.max():.2f}")
