#!/usr/bin/env python3
"""Where each configuration acts: dispatch, interruptions, context switches, C (read-only on the frozen data).

    python3 make_where_it_acts.py

Same data, configurations, cells and warm-up (first N_DROP = 6 jobs of every round) as os-experiments/results_final/make_results_final.py.
SMT is not included. Every number pools the rounds of a cell (multi-core full isolation: both target threads, as in the frozen tables).
Per cell (configuration, period, U); D = P, Q = U * P (budget, us), target of the calibration = 0.7 * Q (headroom_frac in workloads/*/config.yaml):
  disp_p99_rel     p99 of dispatch_latency_us / the same of full isolation (same period, U)
  intr_share       share of jobs interrupted [%]: mid_job_preempt_us > INTERRUPT_US (the median is 1-2 us, a plain timer/clock read; 10 us is a clear intrusion)
  intr_p99_us      p99 of mid_job_preempt_us over the interrupted jobs [us]  (-- if none)
  ctx_share        share of jobs with nonvol_ctxt >= 1 [%]  (involuntary context switch)
  C_med_rel        median C / median C of full isolation
  C_cv             std(C) / mean(C) of the cell, to be compared with the 0.05 calibration threshold (CV_THRESHOLD of run_job.sh)
  miss_C_over_Q    share of the jobs that missed their deadline (deadline_miss = 1) whose C > Q [%]  (-- if no miss)
Also: calibration_check.csv/.tex, median C of full isolation per round against 0.7 Q.
Writes next to this script. Needs numpy, pandas.
"""
import pathlib
import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
OS_DATA = HERE.parent / "data"
BASE_DATA = HERE.parents[2] / "kubedeadline-experiments" / "analysis" / "data"
FULL = "full isolation"
SCEN = [("01", "isolcpus"), ("02", "nohz_full"), ("03", "rcu_nocbs"), ("04", "systemd containment"), ("05", "IRQ steering"), ("08", "frequency pinning"), ("06", "boot-params bundle")]
CONFIGS = [FULL] + [n + " reverted" for _, n in SCEN]
PLACEMENTS = [("single-core", "model1", "model1"), ("multi-core", "model5", "model5-phys")]
SCALES = [("tight", "Tight, $P = 10$ ms", 10_000), ("soft", "Soft, $P = 100$ ms", 100_000)]
UTILS = [0.1, 0.5, 0.7, 0.94]
N_DROP, INTERRUPT_US, HEADROOM, CV_THRESHOLD = 6, 10.0, 0.7, 0.05
COLS = ["disp_p99_rel", "intr_share", "intr_p99_us", "ctx_share"]           # columns of the tex tables; the C columns (C_med_rel, C_cv, miss_C_over_Q) stay in the csv only
LABELS = {"disp_p99_rel": "dispatch p99 / FI", "intr_share": "interrupted jobs [\\%]", "intr_p99_us": "interruption p99 [$\\mu$s]",
          "ctx_share": "jobs with ctx switch [\\%]", "C_med_rel": "median $C$ / FI", "C_cv": "CV of $C$", "miss_C_over_Q": "misses with $C>Q$ [\\%]"}
FMT = {"disp_p99_rel": "{:.2f}", "intr_share": "{:.2f}", "intr_p99_us": "{:.0f}", "ctx_share": "{:.2f}", "C_med_rel": "{:.2f}", "C_cv": "{:.3f}", "miss_C_over_Q": "{:.0f}"}


def load(label, model, base):
    srcs = [(FULL, BASE_DATA / f"{base}.csv")] + [(n + " reverted", OS_DATA / f"{c}-{model}.csv") for c, n in SCEN]
    cells = {}
    for name, path in srcs:
        df = pd.read_csv(path)
        for (scale, u), g in df.groupby(["scale", "U"]):
            if u in UTILS:
                cells[(name, scale, u)] = g[g.job_index >= N_DROP]
    return cells


def stats(g, Q):
    intr = g.mid_job_preempt_us > INTERRUPT_US
    miss = g[g.deadline_miss == 1]
    c = g.C_cputime_us
    return dict(jobs=len(g), disp_p99=np.percentile(g.dispatch_latency_us, 99), intr_share=100 * intr.mean(),
                intr_p99_us=np.percentile(g.mid_job_preempt_us[intr], 99) if intr.any() else np.nan,
                ctx_share=100 * (g.nonvol_ctxt >= 1).mean(), C_med=c.median(), C_cv=c.std() / c.mean(),
                n_miss=len(miss), miss_C_over_Q=100 * (miss.C_cputime_us > Q).mean() if len(miss) else np.nan)


def tex(t, label):
    cols = [(s, u) for s, _, _ in SCALES for u in UTILS]
    out = [r"\begin{longtable}{ll|" + "|".join(["r" * len(UTILS)] * len(SCALES)) + "}", r"\toprule",
           " &  & " + " & ".join(rf"\multicolumn{{{len(UTILS)}}}{{c}}{{{title}}}" for _, title, _ in SCALES) + r" \\",
           "Configuration & Metric & " + " & ".join(f"{u:g}" for _ in SCALES for u in UTILS) + r" \\", r"\midrule", r"\endhead"]
    idx = t.set_index(["configuration", "scale", "U"])
    for i, cfg in enumerate(CONFIGS):
        if i:
            out.append(rf"\cmidrule{{1-{2 + len(cols)}}}")
        for j, m in enumerate(COLS):
            vals = []
            for c in cols:
                v = idx.loc[(cfg, *c), m] if (cfg, *c) in idx.index else np.nan
                vals.append("--" if pd.isna(v) else FMT[m].format(v))
            first = rf"\multirow[t]{{{len(COLS)}}}{{*}}{{{cfg.replace('_', chr(92) + '_')}}}" if j == 0 else ""
            out.append(f"{first} & {LABELS[m]} & " + " & ".join(vals) + r" \\")
    out += [r"\bottomrule", r"\caption{Where each configuration acts, " + label + r". Relative values are against full isolation (FI) at the same period and $U$. "
            rf"Interrupted: $\mathrm{{mid\_job\_preempt}}>{INTERRUPT_US:g}\,\mu$s; interruption p99 over the interrupted jobs. Context switch: involuntary, $\ge 1$ per job. "
            rf"First six jobs after every restart excluded; -- = not run or no such job.}}",
            r"\label{tab:rq1-acts-" + label + r"}", r"\end{longtable}"]
    return "\n".join(out) + "\n"


calib = []
for label, model, base in PLACEMENTS:
    cells = load(label, model, base)
    rows = []
    for cfg in CONFIGS:
        for scale, _, P in SCALES:
            for u in UTILS:
                g = cells.get((cfg, scale, u))
                rows.append(dict(placement=label, configuration=cfg, scale=scale, U=u, **(stats(g, u * P) if g is not None else {})))
    t = pd.DataFrame(rows)
    ref = t[t.configuration == FULL].set_index(["scale", "U"])
    k = list(zip(t.scale, t.U))
    t["disp_p99_rel"] = t.disp_p99.to_numpy() / ref.disp_p99.loc[k].to_numpy()
    t["C_med_rel"] = t.C_med.to_numpy() / ref.C_med.loc[k].to_numpy()
    t["C_cv_over_threshold"] = t.C_cv > CV_THRESHOLD
    t.to_csv(HERE / f"where_it_acts_{label}.csv", index=False, float_format="%.4f")
    (HERE / f"where_it_acts_{label}.tex").write_text(tex(t, label))
    for scale, _, P in SCALES:                                              # calibration check: full isolation, median C per round vs 0.7 Q
        for u in UTILS:
            g = cells[(FULL, scale, u)]
            for rnd, rg in g.groupby("round"):
                calib.append(dict(placement=label, scale=scale, U=u, round=rnd, target_us=HEADROOM * u * P, C_med_us=rg.C_cputime_us.median(),
                                  ratio=rg.C_cputime_us.median() / (HEADROOM * u * P)))
    print(f"\n{label}")
    print(t.pivot_table(index=["scale", "U"], columns="configuration", values="C_cv")[CONFIGS].round(3).to_string())

cal = pd.DataFrame(calib)
cal.to_csv(HERE / "calibration_check.csv", index=False, float_format="%.4f")
summ = cal.groupby(["placement", "scale", "U"]).agg(target_us=("target_us", "first"), rounds=("round", "count"), ratio_min=("ratio", "min"), ratio_max=("ratio", "max")).reset_index()
summ.to_csv(HERE / "calibration_check_summary.csv", index=False, float_format="%.4f")
print("\nCalibration check (median C of full isolation per round / 0.7 Q):")
print(summ.round(3).to_string(index=False))
lines = [r"\begin{table}[ht]", r"\centering", r"\small", r"\begin{tabular}{llrrrr}", r"\toprule", r"Placement & Period & $U$ & $0.7\,Q$ [$\mu$s] & min ratio & max ratio \\", r"\midrule"]
lines += [f"{r.placement} & {r.scale} & {r.U:g} & {r.target_us:.0f} & {r.ratio_min:.3f} & {r.ratio_max:.3f} \\\\" for r in summ.itertuples()]
lines += [r"\bottomrule", r"\end{tabular}", r"\caption{Calibration of full isolation: median $C$ of every round divided by the target $0.7\,Q$, minimum and maximum over the rounds of the cell.}",
          r"\label{tab:rq1-calibration}", r"\end{table}"]
(HERE / "calibration_check.tex").write_text("\n".join(lines) + "\n")
