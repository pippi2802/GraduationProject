#!/usr/bin/env python3
"""One table with the result of the whole procedure-3 online validation (video, segmentation, audio), as CSV and as LaTeX.

    python3 p3_results_table.py                 # writes p3_results_table.csv and p3_results_table.tex next to this script
    python3 p3_results_table.py 0 validation_p4  # the same for the final budgets: p4_results_table.csv / .tex

Reads workload{1,2,3}/validation_p3/iter0/budgets.csv (the budgets that were run) and results/<scenario>/<route>/<level>_<none|memory>/instance*.csv.
One row per workload x scenario x route x level, the worst case over the runs of the cell (without interference / memory enemy, every instance):
  rate verdict    pass: P_ucb(C+delta > Q) <= p;  inconclusive: observed rate <= p but the bound is above it;  FAIL: observed rate > p
  window verdict  pass: share of sliding windows of k jobs with more than k-m misses, counting only the bursts that contain an overrun, <= EPS;  FAIL otherwise
  stalls          platform stalls (W above half a period without a miss before): reported, not budgeted
Needs numpy, pandas, scipy. The LaTeX needs \\usepackage{booktabs} and, for \\resizebox, \\usepackage{graphicx}.
"""
import pathlib, sys
import numpy as np
import pandas as pd
from scipy.stats import beta

HERE = pathlib.Path(__file__).resolve().parent
ITER = sys.argv[1] if len(sys.argv) > 1 else "0"
VALIDATION = sys.argv[2] if len(sys.argv) > 2 else "validation_p3"           # validation_p4 for the final budgets
OUT = "p3_results_table" if VALIDATION == "validation_p3" else VALIDATION.replace("validation_", "") + "_results_table"
WORKLOADS = [("Video", "workload1"), ("Segmentation", "workload2"), ("Audio", "workload3")]
DELTA_MS, CONF, GAP_JOBS, EPS, STALL_FRAC = 0.02, 0.95, 50, 0.01, 0.5      # as in the notebooks (configuration cell)


def read_run(path):
    df = pd.read_csv(path, usecols=["job_id", "cpu_ns", "response_ns", "wait_ns", "deadline_met", "skipped", "warmup"])
    return df[df.warmup == 0].sort_values("job_id").reset_index(drop=True)


def cp_upper(k, n):
    """Clopper-Pearson one-sided upper bound of a probability seen k times in n trials"""
    return 1.0 if k >= n else float(beta.ppf(CONF, k + 1, n - k))


def exceed_test(c, Q, p):
    """overruns C + delta > Q: observed rate and the cluster-aware upper bound (overruns closer than GAP_JOBS form one cluster)"""
    idx = np.flatnonzero(c + DELTA_MS > Q); n = len(c)
    if len(idx) == 0:
        return 0.0, cp_upper(0, n)
    ncl = 1 + int(np.sum(np.diff(idx) > GAP_JOBS))
    return len(idx) / n, cp_upper(ncl, n) * len(idx) / ncl


def window_violation(miss, m, k):
    cs = np.r_[0, np.cumsum(miss.astype(int))]
    return float(((cs[k:] - cs[:-k]) > k - m).mean())


def overrun_misses(bad, over):
    """misses of the bursts of consecutive misses that contain an overrun (what the budget controls)"""
    edges = np.diff(np.r_[0, bad.astype(int), 0])
    out = np.zeros(len(bad), bool)
    for s, e in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if over[s:e].any():
            out[s:e] = True
    return out


def stalls(w, bad, period_ms):
    s = (np.nan_to_num(w, nan=0.0) > STALL_FRAC * period_ms) & (np.convolve(bad.astype(int), [0, 1, 1, 1])[:len(bad)] == 0)
    return int((np.diff(np.r_[0, s.astype(int)]) == 1).sum())


rows = []
for label, folder in WORKLOADS:
    base = HERE / folder / VALIDATION / f"iter{ITER}"
    if not (base / "budgets.csv").exists():
        print(f"skipped {label}: no {base / 'budgets.csv'}")
        continue
    for b in pd.read_csv(base / "budgets.csv").itertuples():
        Q, period_ms = b.runtime_us / 1000, b.period_us / 1000
        runs = []
        for interf in ("none", "memory"):
            for f in sorted((base / "results" / b.scenario / b.route / f"{b.level}_{interf}").glob("instance*.csv")):
                if f.suffix != ".csv" or f.name.endswith(".meta.json"):
                    continue
                df = read_run(f)
                c = (df[df.skipped == 0].cpu_ns / 1e6).to_numpy()
                bad = ((df.skipped == 1) | (df.deadline_met == 0)).to_numpy()
                over = overrun_misses(bad, (df.cpu_ns / 1e6 + DELTA_MS > Q).to_numpy())
                rate, ucb = exceed_test(c, Q, b.p)
                runs.append(dict(rate=rate, ucb=ucb, verdict="pass" if ucb <= b.p else ("inconclusive" if rate <= b.p else "FAIL"),
                                 v_over=window_violation(over, b.m, b.k), v_tot=window_violation(bad, b.m, b.k), stalls=stalls((df.wait_ns / 1e6).to_numpy(), bad, period_ms)))
        if not runs:
            continue
        r = pd.DataFrame(runs)
        rows.append(dict(workload=label, scenario=b.scenario.replace("_core", ""), route="Route " + ("1" if b.route == "route1" else "2"), level=b.level,
                         p=b.p, m=b.m, k=b.k, Q_ms=Q, Q_over_T=Q / period_ms, runs=len(r), P_over=r.rate.max(),
                         rate="FAIL" if (r.verdict == "FAIL").any() else ("inconclusive" if (r.verdict == "inconclusive").any() else "pass"),
                         V_overrun=r.v_over.max(), window="pass" if r.v_over.max() <= EPS else "FAIL", V_total=r.v_tot.max(), stalls=int(r.stalls.sum())))

table = pd.DataFrame(rows)
if table.empty:
    sys.exit("no results found")
table["level"] = pd.Categorical(table.level, ["relaxed", "strict"])
table["workload"] = pd.Categorical(table.workload, [w for w, _ in WORKLOADS])
table["scenario"] = pd.Categorical(table.scenario, ["single", "multi"])
table = table.sort_values(["workload", "scenario", "route", "level"]).reset_index(drop=True)
table.to_csv(HERE / f"{OUT}.csv", index=False)


def tex_cell(v, col):
    if col == "rate" or col == "window":
        return {"pass": "pass", "FAIL": r"\textbf{FAIL}", "inconclusive": "inconcl."}[v]
    if col == "p":
        return f"$10^{{{int(round(np.log10(v)))}}}$"
    if col == "mk":
        return f"({v[0]},{v[1]})"
    if col in ("Q_ms",):
        return f"{v:.2f}"
    if col == "Q_over_T":
        return f"{v:.2f}"
    if col in ("P_over", "V_overrun", "V_total"):
        return f"{100 * v:.2f}\\%"
    return str(v)


cols = [("workload", "Workload"), ("scenario", "Deploy."), ("route", "Variant"), ("level", "Level"), ("p", "$p$"), ("mk", "(m,k)"), ("Q_ms", "$Q$ [ms]"), ("Q_over_T", "$Q/T$"),
        ("P_over", "Overrun rate"), ("V_overrun", "Viol. windows"), ("V_total", "incl. stalls"), ("stalls", "Stalls")]
lines = [r"\begin{table}[ht]", r"\centering", r"\small", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{" + "l" * 4 + "r" * 2 + "r" * 2 + "rcrcrr" + "}", r"\toprule",
         " & ".join(h for _, h in cols) + r" \\", r"\midrule"]
prev = None
for r in table.itertuples():
    if prev is not None and r.workload != prev:
        lines.append(r"\midrule")
    first = r.workload != prev
    vals = []
    for key, _ in cols:
        v = (r.m, r.k) if key == "mk" else getattr(r, key)
        vals.append(tex_cell(v, key) if not (key == "workload" and not first) else "")
    lines.append(" & ".join(vals) + r" \\")
    prev = r.workload
lines += [r"\bottomrule", r"\end{tabular}}",
          r"\caption{Online validation of procedure 3 (iteration 0). Worst case over the runs of each cell (without interference and with the memory enemy, every instance). "
          r"Rate: $P_{ucb}(C+\delta>Q)\le p$. Window: share of sliding windows of $k$ jobs (one second) violating $(m,k)$ because of overruns, at most $1\%$; ``incl. stalls'' also counts stalls and late starts, which the budget does not control.}",
          r"\label{tab:" + OUT.replace("_", "-") + r"}", r"\end{table}"]
(HERE / f"{OUT}.tex").write_text("\n".join(lines) + "\n")

pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
print(table.drop(columns=["p", "m", "k"]).round(4).to_string(index=False))
print(f"\nwritten {HERE / 'p3_results_table.csv'} and {HERE / 'p3_results_table.tex'}")
