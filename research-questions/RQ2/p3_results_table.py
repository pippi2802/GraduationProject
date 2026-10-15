#!/usr/bin/env python3
"""The result of the whole procedure-3 online validation (video, segmentation, audio) as one table and one summary, as CSV and as LaTeX.

    python3 p3_results_table.py                 # writes p3_results_table.csv and p3_results_table.tex next to this script
    python3 p3_results_table.py 0 validation_p4  # the same for the final budgets: p4_results_table.csv / .tex

Reads workload{1,2,3}/<validation_p3|validation_p4>/iter0/budgets.csv (the budgets that were run) and results/<scenario>/<route>/<level>_<none|memory>/instance*.csv.
Variants: stress profile (route1), platform factor (route2b) and, from the earlier validation (workload*/validation_p2/iter0, one budget for every tolerance),
the high-water mark (HWM), judged here with the tolerance and the window requirement of the strict level.
One row per workload x scenario x variant x level, the worst case over the runs of the cell (without interference / memory enemy, every instance):
  Overrun rate     largest observed share of jobs with C + delta > Q
  Viol. windows    share of sliding windows of k jobs with more than k-m misses, counting only the bursts that contain an overrun (what the budget controls)
  incl. stalls     the same counting also stalls and late starts, which the budget does not control
  Stalls           platform stalls (W above half a period without a miss before)
  Over-budget      how much budget there is beyond what the run needed, Q / C_hat - 1 (negative = the budget was too small), worst run of the cell. C_hat = max(C_p, C_(m,k)) of the run:
                   the (1-p) quantile of C + delta seen in the run (just enough for the rate) or its C_(m,k) (just enough for the window requirement), whichever is larger.
                   The CSV also has the two components (OB_rate, OB_window).
The CSV also keeps the rate and window verdicts of each cell; the LaTeX shows the numbers only (the verdicts are for the discussion).
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
VARIANT = {"route1": "Stress profile", "route2b": "Platform factor", "hwm": "HWM"}
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


def window_share(c, Q, m, k):
    cs = np.r_[0, np.cumsum((c + DELTA_MS > Q).astype(int))]
    return float(((cs[k:] - cs[:-k]) > (k - m) // 2).mean()) if len(c) >= k else 0.0


def count_budget(c, m, k, eps, grid=300):
    """C_(m,k) of a series: smallest level with at most eps of the windows of k jobs holding more than (k-m)//2 jobs with C + delta above it"""
    qs = np.geomspace(np.median(c), c.max(), grid)
    lo, hi = 0, grid - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if window_share(c, qs[mid], m, k) <= eps:
            hi = mid
        else:
            lo = mid + 1
    return float(qs[lo])


def judge(folders, Q, period_ms, p, m, k):
    """the runs of one cell (list of folders of instance*.csv) against the budget Q and the requirements p and (m,k)"""
    runs = []
    for d in folders:
        for f in sorted(d.glob("instance*.csv")):
            df = read_run(f)
            c = (df[df.skipped == 0].cpu_ns / 1e6).to_numpy()
            bad = ((df.skipped == 1) | (df.deadline_met == 0)).to_numpy()
            over = overrun_misses(bad, (df.cpu_ns / 1e6 + DELTA_MS > Q).to_numpy())
            rate, ucb = exceed_test(c, Q, p)
            runs.append(dict(ob_p=Q / np.quantile(c + DELTA_MS, 1 - p) - 1, ob_mk=Q / count_budget(c, m, k, EPS) - 1,
                             ob=Q / max(np.quantile(c + DELTA_MS, 1 - p), count_budget(c, m, k, EPS)) - 1, rate=rate, ucb=ucb, verdict="pass" if ucb <= p else ("inconclusive" if rate <= p else "FAIL"),
                             v_over=window_violation(over, m, k), v_tot=window_violation(bad, m, k), stalls=stalls((df.wait_ns / 1e6).to_numpy(), bad, period_ms)))
    if not runs:
        return None
    r = pd.DataFrame(runs)
    return dict(Q_ms=Q, Q_over_T=Q / period_ms, p=p, m=m, k=k, runs=len(r), P_over=r.rate.max(),
                rate="FAIL" if (r.verdict == "FAIL").any() else ("inconclusive" if (r.verdict == "inconclusive").any() else "pass"),
                V_overrun=r.v_over.max(), window="pass" if r.v_over.max() <= EPS else "FAIL", V_total=r.v_tot.max(), stalls=int(r.stalls.sum()),
                OB=r.ob.min(), OB_rate=r.ob_p.min(), OB_window=r.ob_mk.min())


rows = []
for label, folder in WORKLOADS:
    base = HERE / folder / VALIDATION / f"iter{ITER}"
    if not (base / "budgets.csv").exists():
        print(f"skipped {label}: no {base / 'budgets.csv'}")
        continue
    budgets = pd.read_csv(base / "budgets.csv")
    for b in budgets.itertuples():                                                    # stress profile and platform factor, per level
        folders = [base / "results" / b.scenario / b.route / f"{b.level}_{i}" for i in ("none", "memory")]
        res = judge(folders, b.runtime_us / 1000, b.period_us / 1000, b.p, b.m, b.k)
        if res:
            rows.append(dict(workload=label, scenario=b.scenario.replace("_core", ""), variant=VARIANT[b.route], level=b.level, **res))
    # HWM: the budgets of the earlier validation (one budget for every tolerance), judged with the strict level of this workload
    hwm_file = HERE / folder / "validation_p2" / "iter0" / "budgets.csv"
    strict = budgets[budgets.level == "strict"].iloc[0]
    if hwm_file.exists():
        for b in pd.read_csv(hwm_file).query("route == 'hwm'").itertuples():
            folders = [HERE / folder / "validation_p2" / "iter0" / "results" / b.scenario / "hwm" / f"all_{i}" for i in ("none", "memory")]
            res = judge(folders, b.runtime_us / 1000, b.period_us / 1000, strict.p, strict.m, strict.k)
            if res:
                rows.append(dict(workload=label, scenario=b.scenario.replace("_core", ""), variant="HWM", level="--", **res))

table = pd.DataFrame(rows)
if table.empty:
    sys.exit("no results found")
table["variant"] = pd.Categorical(table.variant, ["Stress profile", "Platform factor", "HWM"])
table["level"] = pd.Categorical(table.level, ["relaxed", "strict", "--"])
table["workload"] = pd.Categorical(table.workload, [w for w, _ in WORKLOADS])
table["scenario"] = pd.Categorical(table.scenario, ["single", "multi"])
table = table.sort_values(["workload", "scenario", "variant", "level"]).reset_index(drop=True)
table.to_csv(HERE / f"{OUT}.csv", index=False)

# summary: one line per workload x deployment (level budgets) and per workload x deployment (HWM)
table["group"] = np.where(table.variant == "HWM", "HWM", "Level budgets")
table["within"] = (table.P_over <= table.p) & (table.V_overrun <= EPS)
summary = table.groupby(["workload", "scenario", "group"], observed=True).agg(
    cells=("within", "size"), within=("within", "sum"), Q_min=("Q_over_T", "min"), Q_max=("Q_over_T", "max"), P_over=("P_over", "max"),
    V_overrun=("V_overrun", "max"), V_total=("V_total", "max"), stalls=("stalls", "sum"), OB_min=("OB", "min"), OB_max=("OB", "max")).reset_index()
summary.to_csv(HERE / f"{OUT}_summary.csv", index=False)


def tex_cell(v, col):
    if col == "p":
        return f"$10^{{{int(round(np.log10(v)))}}}$"
    if col == "mk":
        return f"({v[0]},{v[1]})"
    if col in ("Q_ms", "Q_over_T"):
        return f"{v:.2f}"
    if col in ("P_over", "V_overrun", "V_total"):
        return f"{100 * v:.2f}\\%"
    if col == "OB":
        return f"{100 * v:+.0f}\\%"
    if col == "level" and v == "--":
        return "--"
    return str(v)


def longtable(cols, rows_, colspec, caption, label, group_key):
    lines = [r"\begin{table}[ht]", r"\centering", r"\small", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{" + colspec + "}", r"\toprule",
             " & ".join(h for _, h in cols) + r" \\", r"\midrule"]
    prev = None
    for r in rows_:
        g = getattr(r, group_key)
        if prev is not None and g != prev:
            lines.append(r"\midrule")
        vals = []
        for key, _ in cols:
            v = (r.m, r.k) if key == "mk" else getattr(r, key)
            vals.append("" if (key == group_key and g == prev) else tex_cell(v, key))
        lines.append(" & ".join(vals) + r" \\")
        prev = g
    lines += [r"\bottomrule", r"\end{tabular}}", r"\caption{" + caption + "}", r"\label{" + label + "}", r"\end{table}"]
    return lines


cols = [("workload", "Workload"), ("scenario", "Deploy."), ("variant", "Variant"), ("level", "Level"), ("p", "$p$"), ("mk", "(m,k)"), ("Q_ms", "$Q$ [ms]"), ("Q_over_T", "$Q/T$"),
        ("P_over", "Overrun rate"), ("V_overrun", "Viol. windows"), ("V_total", "incl. stalls"), ("stalls", "Stalls"), ("OB", "Over-budget")]
lines = longtable(cols, list(table.itertuples()), "llllrrrrrrrrr",
                  r"Online validation of procedure 3. Variants: budget from the stress profile, from the platform factor, and the high-water mark (HWM, one budget for every tolerance, judged with the tolerance and window requirement of the strict level). "
                  r"Worst case over the runs of each cell (without interference and with the memory enemy, every instance). Overrun rate: share of jobs with $C+\delta>Q$. "
                  r"Viol. windows: share of sliding windows of $k$ jobs (one second) violating $(m,k)$ because of overruns; ``incl. stalls'' also counts stalls and late starts, which the budget does not control. Over-budget: $Q/\hat C-1$ in the worst run of the cell, with $\hat C=\max(C_p,C_{(m,k)})$ of that run, the budget that would just have met both requirements; negative means the budget was too small.",
                  "tab:" + OUT.replace("_", "-"), "workload")

# the summary table
sum_rows = []
for r in summary.itertuples():
    sum_rows.append(type("R", (), dict(workload=r.workload, scenario=r.scenario, group=r.group, cells=f"{int(r.within)}/{r.cells}", Q=f"{r.Q_min:.2f}--{r.Q_max:.2f}" if r.Q_max - r.Q_min > 0.005 else f"{r.Q_min:.2f}",
                                       P_over=r.P_over, V_overrun=r.V_overrun, V_total=r.V_total, stalls=r.stalls,
                                       OBr=f"{100 * r.OB_min:+.0f}\\% / {100 * r.OB_max:+.0f}\\%"))())
sum_cols = [("workload", "Workload"), ("scenario", "Deploy."), ("group", "Budgets"), ("Q", "$Q/T$"), ("cells", "Cells within $p$ and $\\varepsilon$"), ("P_over", "Worst overrun rate"),
            ("V_overrun", "Worst viol. windows"), ("V_total", "incl. stalls"), ("stalls", "Stalls"), ("OBr", "Over-budget min / max")]
lines += [""] + longtable(sum_cols, sum_rows, "lllrrrrrrr",
                          r"Summary per workload and deployment. A cell is within the requirements when its observed overrun rate is at most $p$ and the share of violating windows at most $\varepsilon=1\%$ (overruns only).",
                          "tab:" + OUT.replace("_", "-") + "-summary", "workload")
(HERE / f"{OUT}.tex").write_text("\n".join(lines) + "\n")

pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
print(table.drop(columns=["p", "m", "k", "group", "within"]).round(4).to_string(index=False))
print("\n--- summary:")
print(summary.round(4).to_string(index=False))
print("\n--- highlights:")
for r in summary.itertuples():
    what = "all" if r.within == r.cells else f"{int(r.within)} of"
    print(f"{r.workload}, {r.scenario}-core, {r.group}: {what} {r.cells} cells within p and eps; overrun rate <= {100 * r.P_over:.2f}%, violating windows <= {100 * r.V_overrun:.2f}% "
          f"({100 * r.V_total:.2f}% with stalls), Q/T {r.Q_min:.2f}-{r.Q_max:.2f}, {r.stalls} stalls")
print(f"\nwritten {HERE / (OUT + '.csv')}, {HERE / (OUT + '_summary.csv')} and {HERE / (OUT + '.tex')}")
