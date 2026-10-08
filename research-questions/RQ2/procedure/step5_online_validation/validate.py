#!/usr/bin/env python3
"""Step 5: online validation. Compares what the budgets of step 4 promise with what the runs on the cluster showed.

    python3 validate.py matrix      what to run: the reservation (runtime, period) of every run, and the folder to save its results in
    python3 validate.py check       the validation of the results you saved

Save each run's CSVs (instance0.csv, instance1.csv, ...) in   results/<scenario>/<route>/<p>_<interference>/
    route: route1, route2b or hwm        p: p1e-1, p1e-2, p1e-3 (the HWM route has one budget for every p: hwm/all_<interference>)
    interference: none, or memory (the memory enemy running during the run)
Reserve runtime_us of period_us for the run (the matrix has it) and run the workload with a few tens of thousands of jobs.
Reads ../step4_parameter_derivation/results/budgets.csv. Writes the table to report/.

What is checked. The tolerance p is the admissible probability that a job's execution time exceeds its budget, P(C > B*) <= p, with B* the
budget of step 4 (the reserved runtime). One table, one row per scenario, route and p, per interference condition:
    P(C <= B*)        share of the executed jobs whose cpu_ns is within the reserved runtime (worst instance); the budget is valid when it is >= 1 - p
    over-budget %     B* / B_oracle - 1, with B_oracle the (1-p) quantile of C in that same run (the smallest budget that would have met p there;
                      the largest over the instances, since they share one reservation). Negative: the run needed more than B*.
    deadline miss     share of the jobs with R > T, or skipped (worst instance). Reported, not judged: it also contains the misses that are not
                      caused by an overrun (platform stalls, late starts, reservation overheads).
Warm-up jobs are left out. The HWM route has one budget for every p, so its run is shown at every p."""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STEP4 = HERE.parent / "step4_parameter_derivation" / "results"


def route_dir(label):
    return "hwm" if label == "HWM" else "route1" if label == "Route 1" else "route2b"


def p_tag(p):
    k = round(-math.log10(p))
    return f"p1e-{k}" if abs(p - 10.0 ** -k) < 1e-12 else f"p{p:g}"


class Budgets:
    """The budgets of step 4, and where the online run of each one is expected."""

    def __init__(self, path):
        if not Path(path).exists():
            sys.exit(f"{path} not found: run step 4 first")
        d = pd.read_csv(path)
        d["route_dir"] = d.route.map(route_dir)
        self.table = d

    def folder(self, scenario, route_dir, p, cond):
        return Path(scenario) / route_dir / (f"all_{cond}" if route_dir == "hwm" else f"{p_tag(p)}_{cond}")

    def matrix(self):
        rows = []
        for r in self.table.itertuples():
            if r.route_dir == "hwm" and r.p != self.table[self.table.route_dir == "hwm"].p.max():
                continue                                             # one budget for every p: one pair of runs
            for cond in ("none", "memory"):
                rows.append(dict(scenario=r.scenario, route=r.route, p="all" if r.route_dir == "hwm" else r.p, interference=cond, runtime_us=r.runtime_us,
                                 period_us=r.period_us, Q_over_T=round(r.Q_over_T, 4), admitted=r.admitted,
                                 save_results_in=str(Path("results") / self.folder(r.scenario, r.route_dir, r.p, cond))))
        return pd.DataFrame(rows)


class OnlineRun:
    """One online run (a folder with instance*.csv) against the budget B* that was reserved for it."""

    def __init__(self, folder, runtime_us, period_us, p):
        self.runtime_us, self.period_us, self.p = runtime_us, period_us, p
        self.frames = [pd.read_csv(f, usecols=["cpu_ns", "response_ns", "skipped", "warmup"]) for f in sorted(folder.glob("instance*.csv"))]

    def summary(self):
        within, missed, oracle = [], [], []
        for df in self.frames:
            df = df[df.warmup == 0]
            c = df.cpu_ns[df.skipped == 0].dropna().to_numpy(dtype=float) / 1e3                # us, executed jobs
            within.append(float((c <= self.runtime_us).mean()))
            missed.append(float(((df.skipped == 1) | (df.response_ns > self.period_us * 1e3)).mean()))
            oracle.append(float(np.quantile(c, 1 - self.p)))
        return {"P(C <= B*)": min(within), "over-budget %": 100 * (self.runtime_us / max(oracle) - 1), "deadline miss (R > T)": max(missed)}


class OnlineValidator:
    def __init__(self, budgets, results_dir):
        self.b, self.dir = budgets, Path(results_dir)

    def table(self):
        rows, missing = [], 0
        for r in self.b.table.itertuples():
            for cond in ("none", "memory"):
                folder = self.dir / self.b.folder(r.scenario, r.route_dir, r.p, cond)
                if not list(folder.glob("instance*.csv")):
                    missing += 1
                    continue
                rows.append(dict(scenario=r.scenario, route=r.route, p=r.p, interference=cond,
                                 **OnlineRun(folder, r.runtime_us, r.period_us, r.p).summary()))
        if not rows:
            sys.exit(f"no run found under {self.dir}: save the results as described by `python3 validate.py matrix`")
        t = pd.DataFrame(rows).pivot_table(index=["scenario", "route", "p"], columns="interference", aggfunc="first")
        t = t.swaplevel(axis=1).reindex(columns=pd.MultiIndex.from_product(
            [[c for c in ("none", "memory") if c in t.columns.get_level_values(1)], ["P(C <= B*)", "over-budget %", "deadline miss (R > T)"]]))
        return t.sort_index(ascending=[True, True, False]), missing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["matrix", "check"])
    ap.add_argument("--step4", default=str(STEP4), help="step 4's results folder")
    ap.add_argument("--results", default=str(HERE / "results"))
    ap.add_argument("--out", default=str(HERE / "report"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    budgets = Budgets(Path(a.step4) / "budgets.csv")

    def show(name, df, title, sci=()):
        df.to_csv(out / f"{name}.csv")
        shown = df.round({c: 3 for c in df.select_dtypes("number").columns if c not in sci})        # the sci columns keep their precision
        print(f"\n[{name}] {title}\n{shown.to_string(formatters={c: '{:.1e}'.format for c in sci})}")

    if a.command == "matrix":
        show("run_matrix", budgets.matrix().set_index(["scenario", "route", "p", "interference"]),
             "reserve runtime_us of every period_us, run the workload, save the CSVs in save_results_in (relative to this folder)")
        return

    t, missing = OnlineValidator(budgets, a.results).table()
    t.to_csv(out / "online_validation.csv")
    fmt = {c: ("{:.5f}" if c[1] == "P(C <= B*)" else "{:.1f}" if c[1] == "over-budget %" else "{:.1e}").format for c in t.columns}
    print("\n[online_validation] per route and p: P(C <= B*) (valid when >= 1 - p), over-budget against the run's own (1-p) quantile, "
          "deadline-miss rate (R > T or skipped; reported, not judged)")
    print(t.to_string(formatters=fmt))
    print(f"\n{missing} expected runs not found. Table in {(out / 'online_validation.csv').resolve()}")


if __name__ == "__main__":
    main()
