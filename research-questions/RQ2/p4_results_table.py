#!/usr/bin/env python3
"""The result of the online validation p4 (the final budgets of procedure 3; video, segmentation, audio) as one table and one summary, as CSV and as LaTeX.

    python3 p4_results_table.py                 # writes p4_results_table.csv, p4_results_table_summary.csv and p4_results_table.tex next to this script
    python3 p4_results_table.py 0 workload4     # only one workload (iteration 0): writes p4_results_table_workload4.csv / _summary.csv / .tex

Same script as p3_results_table.py, reading validation_p4 instead of validation_p3.

Reads workload{1,2,3}/validation_p4/iter0/budgets.csv (the budgets that were run) and results/<scenario>/<route>/<level>_<none|memory>/instance*.csv.
Variants: stress profile (route1), platform factor (route2b) and, from the earlier validation (workload*/validation_p2/iter0, one budget for every tolerance),
the high-water mark (HWM), judged here with the tolerance and the window requirement of the strict level.
One row per workload x scenario x variant x level, the worst case over the runs of the cell (without interference / memory enemy, every instance):
  Overrun rate     largest observed share of jobs with C > Q
  Viol. windows    share of sliding windows of k jobs with more than k-m overruns (C > Q), as in the derivation (offlineValidation.Replay.mk_worst)
The guarantee (p and (m,k)) is judged on C > Q only. Its consequence is reported in a second table (lost releases = R > D or skipped):
  Deadline miss    share of jobs that ran with R > D;  Skipped  share of releases skipped;  Lost  both together
  Viol. windows    share of sliding windows of k jobs with more than k-m lost releases;  Stalls  platform stalls (W above half a period without a miss before)
  Over-budget      how much budget there is beyond what the run needed, Q / C_hat - 1 (negative = the budget was too small), worst run of the cell. C_hat = max(C_p, C_(m,k)) of the run:
                   the (1-p) quantile of C seen in the run (just enough for the rate) or its C_(m,k) (just enough for the window requirement), whichever is larger.
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
VALIDATION = "validation_p4"                                                 # the final budgets of procedure 3
OUT = "p4_results_table"
WORKLOADS = [("Video", "workload1"), ("Segmentation", "workload2"), ("Audio", "workload3"), ("LiDAR", "workload4")]
if len(sys.argv) > 2:                                                        # one workload only, in its own files
    WORKLOADS = [w for w in WORKLOADS if w[1] == sys.argv[2]]
    OUT += "_" + sys.argv[2]
VARIANT = {"route1": "Stress profile", "route2b": "Platform factor", "hwm": "HWM",
           "variant1": "Stress profile", "variant2": "Platform factor", "variant3": "HWM"}   # workloads 1-3 name the column route (old files), workload 4 variant
CONF, GAP_JOBS, EPS, STALL_FRAC = 0.95, 50, 0.01, 0.5      # as in the notebooks (configuration cell)


def read_run(path):
    df = pd.read_csv(path, usecols=["job_id", "cpu_ns", "response_ns", "wait_ns", "deadline_met", "skipped", "warmup"])
    return df[df.warmup == 0].sort_values("job_id").reset_index(drop=True)


def cp_upper(k, n):
    """Clopper-Pearson one-sided upper bound of a probability seen k times in n trials"""
    return 1.0 if k >= n else float(beta.ppf(CONF, k + 1, n - k))


def exceed_test(c, Q, p):
    """overruns C > Q: observed rate and the cluster-aware upper bound (overruns closer than GAP_JOBS form one cluster)"""
    idx = np.flatnonzero(c > Q); n = len(c)
    if len(idx) == 0:
        return 0.0, cp_upper(0, n)
    ncl = 1 + int(np.sum(np.diff(idx) > GAP_JOBS))
    return len(idx) / n, cp_upper(ncl, n) * len(idx) / ncl


def window_violation(miss, m, k):
    cs = np.r_[0, np.cumsum(miss.astype(int))]
    return float(((cs[k:] - cs[:-k]) > k - m).mean())


def stalls(w, bad, period_ms):
    s = (np.nan_to_num(w, nan=0.0) > STALL_FRAC * period_ms) & (np.convolve(bad.astype(int), [0, 1, 1, 1])[:len(bad)] == 0)
    return int((np.diff(np.r_[0, s.astype(int)]) == 1).sum())


def window_share(c, Q, m, k):
    cs = np.r_[0, np.cumsum((c > Q).astype(int))]
    return float(((cs[k:] - cs[:-k]) > (k - m) // 2).mean()) if len(c) >= k else 0.0


def count_budget(c, m, k, eps, grid=300):
    """C_(m,k) of a series: smallest level with at most eps of the windows of k jobs holding more than (k-m)//2 jobs with C above it"""
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
            bad = ((df.skipped == 1) | (df.deadline_met == 0)).to_numpy()                 # lost release: R > D or skipped
            late = ((df.skipped == 0) & (df.deadline_met == 0)).to_numpy()
            over = c > Q                                                                 # overrun series of the executed jobs, as in the derivation
            rate, ucb = exceed_test(c, Q, p)
            runs.append(dict(ob_p=Q / np.quantile(c, 1 - p) - 1, ob_mk=Q / count_budget(c, m, k, EPS) - 1,
                             ob=Q / max(np.quantile(c, 1 - p), count_budget(c, m, k, EPS)) - 1, rate=rate, ucb=ucb, verdict="pass" if ucb <= p else ("inconclusive" if rate <= p else "FAIL"),
                             v_over=window_violation(over, m, k) if len(over) >= k else 0.0, v_tot=window_violation(bad, m, k),
                             miss=late.mean(), skip=(df.skipped == 1).mean(), lost=bad.mean(), stalls=stalls((df.wait_ns / 1e6).to_numpy(), bad, period_ms)))
    if not runs:
        return None
    r = pd.DataFrame(runs)
    return dict(Q_ms=Q, Q_over_T=Q / period_ms, p=p, m=m, k=k, runs=len(r), P_over=r.rate.max(),
                rate="FAIL" if (r.verdict == "FAIL").any() else ("inconclusive" if (r.verdict == "inconclusive").any() else "pass"),
                V_overrun=r.v_over.max(), window="pass" if r.v_over.max() <= EPS else "FAIL", V_total=r.v_tot.max(), miss=r.miss.max(), skip=r.skip.max(), lost=r.lost.max(), stalls=int(r.stalls.sum()),
                OB=r.ob.min(), OB_rate=r.ob_p.min(), OB_window=r.ob_mk.min())


rows = []
for label, folder in WORKLOADS:
    # a cell is read from the newest iteration (up to ITER) that has results for it; the others stay with the budget they were run with
    # (a recalibration or the monotone rule re-runs only the cells whose budget changed, in iter1, iter2, ...)
    base = HERE / folder / VALIDATION / "iter0"
    if not (base / "budgets.csv").exists():
        print(f"skipped {label}: no {base / 'budgets.csv'}")
        continue
    budgets = pd.read_csv(base / "budgets.csv").rename(columns={"variant": "route"})
    cells = {}
    for it in range(int(ITER) + 1):
        d = HERE / folder / VALIDATION / f"iter{it}"
        if not (d / "budgets.csv").exists():
            continue
        for b in pd.read_csv(d / "budgets.csv").rename(columns={"variant": "route"}).itertuples():     # stress profile and platform factor, per level
            folders = [d / "results" / b.scenario / b.route / f"{'strict' if b.route in ('hwm', 'variant3') else b.level}_{i}" for i in ("none", "memory")]   # HWM of workload 4: one run, judged on both levels
            res = judge(folders, b.runtime_us / 1000, b.period_us / 1000, b.p, b.m, b.k)
            if res:
                cells[(b.scenario, b.route, b.level)] = dict(workload=label, scenario=b.scenario.replace("_core", ""), variant=VARIANT[b.route], level=b.level, iteration=it, **res)
    rows.extend(cells.values())
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
    V_overrun=("V_overrun", "max"), V_total=("V_total", "max"), miss=("miss", "max"), skip=("skip", "max"), lost=("lost", "max"), stalls=("stalls", "sum"), OB_min=("OB", "min"), OB_max=("OB", "max")).reset_index()
summary.to_csv(HERE / f"{OUT}_summary.csv", index=False)


def tex_cell(v, col):
    if col == "p":
        return f"$10^{{{int(round(np.log10(v)))}}}$"
    if col == "mk":
        return f"({v[0]},{v[1]})"
    if col in ("Q_ms", "Q_over_T"):
        return f"{v:.2f}"
    if col in ("miss", "skip", "lost"):
        return f"{100 * v:.3f}\\%"
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
        ("P_over", "Overrun rate"), ("V_overrun", "Viol. windows"), ("OB", "Over-budget")]
lines = longtable(cols, list(table.itertuples()), "llllrrrrrrr",
                  r"Online validation of procedure 3 with its final budgets (validation\_p4). Variants: budget from the stress profile, from the platform factor, and the high-water mark (HWM, one budget for every tolerance, judged with the tolerance and window requirement of the strict level). "
                  r"Worst case over the runs of each cell (without interference and with the memory enemy, every instance). Overrun rate: share of jobs with $C>Q$. "
                  r"Viol. windows: share of sliding windows of $k$ jobs (one second) with more than $k-m$ jobs with $C>Q$, the same criterion as in the derivation. Both requirements ($p$ and $(m,k)$) are judged on $C>Q$ only; their consequence on releases is in Table~\ref{tab:p4-results-table-lost}. Over-budget: $Q/\hat C-1$ in the worst run of the cell, with $\hat C=\max(C_p,C_{(m,k)})$ of that run, the budget that would just have met both requirements; negative means the budget was too small.",
                  "tab:" + OUT.replace("_", "-"), "workload")

# the summary table
sum_rows = []
for r in summary.itertuples():
    sum_rows.append(type("R", (), dict(workload=r.workload, scenario=r.scenario, group=r.group, cells=f"{int(r.within)}/{r.cells}", Q=f"{r.Q_min:.2f}--{r.Q_max:.2f}" if r.Q_max - r.Q_min > 0.005 else f"{r.Q_min:.2f}",
                                       P_over=r.P_over, V_overrun=r.V_overrun, V_total=r.V_total, stalls=r.stalls,
                                       OBr=f"{100 * r.OB_min:+.0f}\\% / {100 * r.OB_max:+.0f}\\%"))())
sum_cols = [("workload", "Workload"), ("scenario", "Deploy."), ("group", "Budgets"), ("Q", "$Q/T$"), ("cells", "Cells within $p$ and $\\varepsilon$"), ("P_over", "Worst overrun rate"),
            ("V_overrun", "Worst viol. windows"), ("OBr", "Over-budget min / max")]
lines += [""] + longtable(sum_cols, sum_rows, "lllrrrrr",
                          r"Summary per workload and deployment. A cell is within the requirements when its observed overrun rate is at most $p$ and the share of violating windows at most $\varepsilon=1\%$ (both on $C>Q$).",
                          "tab:" + OUT.replace("_", "-") + "-summary", "workload")

# consequence table: lost releases (R > D or skipped) per workload x deployment x variant x level
lost_cols = [("workload", "Workload"), ("scenario", "Deploy."), ("variant", "Variant"), ("level", "Level"), ("p", "$p$"), ("mk", "(m,k)"), ("miss", "Deadline miss ($R>D$)"),
             ("skip", "Skipped"), ("lost", "Lost releases"), ("V_total", "Viol. windows (lost)"), ("stalls", "Stalls")]
lines += [""] + longtable(lost_cols, list(table.itertuples()), "llllrrrrrrr",
                          r"Consequence of the budgets of Table~\ref{tab:p4-results-table} on the releases, same runs and worst case. Deadline miss: share of jobs that ran with $R>D$. Skipped: share of releases skipped (the job was still running). "
                          r"Lost releases: both together. Viol. windows (lost): share of sliding windows of $k$ jobs with more than $k-m$ lost releases. Stalls: platform stalls (VM stalls, late starts), not controlled by the budget. Reported, not judged.",
                          "tab:" + OUT.replace("_", "-") + "-lost", "workload")
table[["workload", "scenario", "variant", "level", "p", "m", "k", "miss", "skip", "lost", "V_total", "stalls"]].to_csv(HERE / f"{OUT}_lost.csv", index=False)
(HERE / f"{OUT}.tex").write_text("\n".join(lines) + "\n")

pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
print(table.drop(columns=["p", "m", "k", "group", "within"]).round(4).to_string(index=False))
print("\n--- summary:")
print(summary.round(4).to_string(index=False))
print("\n--- highlights:")
for r in summary.itertuples():
    what = "all" if r.within == r.cells else f"{int(r.within)} of"
    print(f"{r.workload}, {r.scenario}-core, {r.group}: {what} {r.cells} cells within p and eps; overrun rate <= {100 * r.P_over:.2f}%, violating windows <= {100 * r.V_overrun:.2f}% "
          f"(lost-release windows {100 * r.V_total:.2f}%, miss {100 * r.miss:.3f}%, skipped {100 * r.skip:.3f}%), Q/T {r.Q_min:.2f}-{r.Q_max:.2f}, {r.stalls} stalls")
print(f"\nwritten {HERE / (OUT + '.csv')}, {HERE / (OUT + '_summary.csv')} and {HERE / (OUT + '.tex')}")
