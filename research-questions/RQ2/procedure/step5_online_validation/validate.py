#!/usr/bin/env python3
"""Step 5: online validation. Compares what the budgets of step 4 promise with what the runs on the cluster showed.

    python3 validate.py matrix      what to run: the reservation (runtime, period) of every run, and the folder to save its results in
    python3 validate.py check       the validation of the results you saved

Save each run's CSVs (instance0.csv, instance1.csv, ...) in   results/<scenario>/<route>/<p>_<interference>/
    route: route1, route2b or hwm        p: p1e-1, p1e-2, p1e-3 (the HWM route has one budget for every p: hwm/all_<interference>)
    interference: none, or memory (the memory enemy running during the run)
Reserve runtime_us of period_us for the run (the matrix has it) and run the workload with a few tens of thousands of jobs.
Reads ../step4_parameter_derivation/results/{budgets,p_floor,burst_check}.csv. Writes the tables to report/.

Pass rule, fixed before looking at the results. A MISS is a late job (deadline_met = 0) or a skipped job; a miss EVENT is a run of consecutive
misses. An event that contains a job with C > Q* (cpu_ns above the reserved runtime) is a BUDGET MISS; any other event is a PLATFORM STALL: the
budget cannot prevent it, so it is reported apart and not counted. A run passes at tolerance p when its budget-miss rate (worst instance) is at
most p: PASS if the 95% Clopper-Pearson upper bound is also at most p, "pass?" if only the point estimate is, FAIL if the point estimate exceeds p."""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import beta

HERE = Path(__file__).resolve().parent
STEP4 = HERE.parent / "step4_parameter_derivation" / "results"
ACCOUNTING_MARGIN = 0.96                 # jobs are not late below this x Q* (a property of the reservation); used for the stall classification only


def route_dir(label):
    return "hwm" if label == "HWM" else "route1" if label == "Route 1" else "route2b"


def p_tag(p):
    k = round(-math.log10(p))
    return f"p1e-{k}" if abs(p - 10.0 ** -k) < 1e-12 else f"p{p:g}"


def cp_upper(k, n, conf=0.95):
    """one-sided Clopper-Pearson upper bound for k events in n jobs"""
    return np.nan if n == 0 else (1 - (1 - conf) ** (1 / n) if k == 0 else beta.ppf(conf, k + 1, n - k))


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
    """One online run (a folder with instance*.csv) analysed against the budget that was reserved for it."""

    def __init__(self, folder, runtime_us, p):
        self.runtime_us, self.p = runtime_us, p
        self.frames = [pd.read_csv(f, usecols=["skipped", "deadline_met", "cpu_ns"]) for f in sorted(folder.glob("instance*.csv"))]

    def instance(self, df):
        n = len(df)
        cpu = df.cpu_ns.to_numpy(dtype=float) / 1e3                                        # us
        skipped = (df.skipped == 1).to_numpy()
        late = ((df.skipped == 0) & (df.deadline_met == 0)).to_numpy()
        miss = skipped | late
        first = miss & ~np.concatenate(([False], miss[:-1]))
        ev, n_ev = np.cumsum(first), int(first.sum())
        lens = np.bincount(ev[miss], minlength=n_ev + 1)

        def budget_events(threshold):                                                      # events with a job above threshold x Q*
            be = np.zeros(n_ev + 1, dtype=bool)
            hit = (~skipped) & (cpu / self.runtime_us > threshold) & miss
            if hit.any():
                be[ev[hit]] = True
            be[0] = False
            return be

        be, bm = budget_events(1.0), budget_events(ACCOUNTING_MARGIN)
        r, ex = cpu / self.runtime_us, ~skipped
        bands = [ex & (r <= ACCOUNTING_MARGIN), ex & (r > ACCOUNTING_MARGIN) & (r <= 1.0), ex & (r > 1.0)]
        oracle = float(np.quantile(cpu[~np.isnan(cpu)], 1 - self.p))                       # smallest budget that meets p in this run
        return dict(n=n, budget_misses=int((miss & be[ev]).sum()), budget_misses_margin=int((miss & bm[ev]).sum()),
                    budget_longest=int(lens[be].max()) if be.any() else 0, stall_events=n_ev - int(bm.sum()), stall_jobs=int(miss.sum() - (miss & bm[ev]).sum()),
                    **{f"n_{k}": int(b.sum()) for k, b in zip(("lo", "mid", "hi"), bands)}, **{f"late_{k}": int((b & late).sum()) for k, b in zip(("lo", "mid", "hi"), bands)},
                    over_budget=self.runtime_us / oracle - 1)

    def worst(self):
        """the instance with the highest budget-miss rate"""
        rows = [self.instance(df) for df in self.frames]
        return max(rows, key=lambda x: x["budget_misses"] / x["n"])


class OnlineValidator:
    def __init__(self, budgets, results_dir, p_floor, burst):
        self.b, self.dir, self.p_floor, self.burst = budgets, Path(results_dir), p_floor, burst

    def runs(self):
        rows, missing = [], 0
        for r in self.b.table.itertuples():
            for cond in ("none", "memory"):
                folder = self.dir / self.b.folder(r.scenario, r.route_dir, r.p, cond)
                if not list(folder.glob("instance*.csv")):
                    missing += 1
                    continue
                w = OnlineRun(folder, r.runtime_us, r.p).worst()
                rate = w["budget_misses"] / w["n"]
                upper = cp_upper(w["budget_misses"], w["n"])
                rate_m = w["budget_misses_margin"] / w["n"]
                rows.append(dict(scenario=r.scenario, route=r.route, route_dir=r.route_dir, p=r.p, cond=cond, runtime_us=r.runtime_us, **w, rate=rate, miss_over_p=rate / r.p,
                                 verdict="FAIL" if rate > r.p else ("PASS" if upper <= r.p else "pass?"),
                                 verdict_margin="FAIL" if rate_m > r.p else ("PASS" if cp_upper(w["budget_misses_margin"], w["n"]) <= r.p else "pass?")))
        if not rows:
            sys.exit(f"no run found under {self.dir}: save the results as described by `python3 validate.py matrix`")
        return pd.DataFrame(rows), missing

    def verdicts(self, runs):
        t = runs.pivot_table(index=["scenario", "route", "p"], columns="cond", values=["miss_over_p", "verdict"], aggfunc="first")
        t.columns = [f"{c[1]}: {c[0]}" for c in t.columns]
        return t.sort_index(ascending=[True, True, False])

    def assumption(self, runs):
        """is a job late only when it needs more CPU time than the reserved budget? (a HWM run counts once)"""
        u = runs[(runs.route_dir != "hwm") | (runs.p == runs[runs.route_dir == "hwm"].p.max())]
        s = u[["n_lo", "late_lo", "n_mid", "late_mid", "n_hi", "late_hi"]].sum()
        t = pd.DataFrame({"jobs": [s.n_lo, s.n_mid, s.n_hi], "late": [s.late_lo, s.late_mid, s.late_hi]},
                         index=[f"C < {ACCOUNTING_MARGIN:.0%} of Q*", f"{ACCOUNTING_MARGIN:.0%} to 100% of Q*", "C > Q*"]).astype(int)
        t["late %"] = 100 * t.late / t.jobs
        return t

    def stalls(self, runs):
        """clear platform stalls (events with no job above the accounting margin) against p_floor of the profiling"""
        u = runs[(runs.route_dir != "hwm") | (runs.p == runs[runs.route_dir == "hwm"].p.max())]
        g = u.groupby("scenario").agg(jobs=("n", "sum"), stall_events=("stall_events", "sum"), jobs_lost=("stall_jobs", "sum"))
        g["events per job"] = g.stall_events / g.jobs
        if self.p_floor is not None:
            bound = self.p_floor[self.p_floor.runs == "all runs"].set_index("scenario")["95% upper"]
            g["profiling bound (95%)"] = g.index.map(bound)
            g["above bound"] = g["events per job"] > g["profiling bound (95%)"]
        return g

    def online_vs_offline(self, runs):
        """the memory runs against the burst check of step 4 (replay of the stressed profiling traces at the same budget)"""
        if self.burst is None:
            return None
        m = runs[runs.cond == "memory"].set_index(["scenario", "route", "p"])
        off = self.burst.set_index(["scenario", "route", "p"]).rename(columns={"miss_over_p": "offline miss/p", "max_consec": "offline longest burst"})
        t = m[["miss_over_p", "budget_longest"]].rename(columns={"miss_over_p": "online miss/p", "budget_longest": "online longest burst"}).join(off[["offline miss/p", "offline longest burst"]])
        return t.sort_index(ascending=[True, True, False])

    def over_budget(self, runs):
        """Q* / Q_oracle - 1 in %, the oracle being the smallest budget that would have met p in that same run"""
        t = runs.pivot_table(index=["scenario", "route", "p"], columns="cond", values="over_budget").mul(100)
        t = t.rename(columns={"none": "no interference", "memory": "memory enemy"})
        mean = t.groupby(["scenario", "route"]).mean().assign(p="mean")
        return pd.concat([t.reset_index(), mean.reset_index()]).astype({"p": str}).set_index(["scenario", "route", "p"]).sort_index()


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

    pf = Path(a.step4) / "p_floor.csv"
    bs = Path(a.step4) / "burst_check.csv"
    v = OnlineValidator(budgets, a.results, pd.read_csv(pf) if pf.exists() else None, pd.read_csv(bs) if bs.exists() else None)
    runs, missing = v.runs()
    show("online_verdicts", v.verdicts(runs), "budget-miss rate / p (below 1 is within the tolerance) and verdict, per interference; the pass rule is in the header of validate.py")
    show("scheduler_assumption", v.assumption(runs), "is a job late only when C > Q*?  late % should be ~0 below the margin and ~100 above Q*")
    show("platform_stalls", v.stalls(runs), "stalls that no budget prevents, against p_floor of the profiling (above bound: look at the scheduler, not the platform)", sci=("events per job", "profiling bound (95%)"))
    t = v.online_vs_offline(runs)
    if t is not None:
        show("online_vs_offline", t, "memory runs against the offline burst check of step 4 (the offline model has no skip cascade, so online bursts may be longer)")
    show("over_budgeting", v.over_budget(runs), "Q* / Q_oracle - 1 in %: how much more than needed was reserved (negative: the run needed more)")
    runs.drop(columns=["route_dir"]).to_csv(out / "online_runs.csv", index=False)
    cells = runs.groupby(["scenario", "route", "p"]).verdict.agg(lambda s: "FAIL" if (s == "FAIL").any() else ("pass?" if (s == "pass?").any() else "PASS"))
    changed = int((runs.verdict != runs.verdict_margin).sum())
    print(f"\n{len(runs)} runs analysed ({missing} expected runs not found). Budget x tolerance cells: {cells.value_counts().to_dict()}. "
          f"With the accounting margin {changed} of {len(runs)} verdicts change. Tables in {out.resolve()}")


if __name__ == "__main__":
    main()
