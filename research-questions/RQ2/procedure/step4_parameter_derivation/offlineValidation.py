"""Offline validation of the bounds and the budgets on traces: Replay, HeldOutReplay, BurstCheck, BoundCheck, LeaveOneOut, StressRunCheck.
Every validation returns its table and a list of checks (see report.check)."""
import numpy as np
import pandas as pd

from report import check


class Replay:
    """Budget overruns C > Q on a trace: overrun rate / p, longest run of overruns, worst-case (m, k)."""

    def __init__(self, cfg):
        self.cfg = cfg

    @staticmethod
    def mk_worst(over, k):
        """minimum number of jobs within the budget (C <= Q) in any window of k consecutive jobs"""
        if len(over) < k:
            return np.nan
        return int(np.convolve((~over).astype(np.int64), np.ones(k, dtype=np.int64), mode="valid").min())

    @staticmethod
    def max_consecutive(over):
        if not over.any():
            return 0
        e = np.diff(np.concatenate(([0], over.astype(np.int8), [0])))
        return int((np.flatnonzero(e == -1) - np.flatnonzero(e == 1)).max())

    def run(self, x, q, p):
        over = x > q
        out = dict(overrun_rate=over.mean(), overrun_over_p=over.mean() / p, max_consec=self.max_consecutive(over))
        for k in self.cfg.k_list:
            out[f"mk_worst_k{k}"] = self.mk_worst(over, k)
        return out

    def summarise(self, rows, with_over_budget):
        """worst case over runs and instances, for the test tolerances"""
        d = pd.DataFrame(rows)
        d = d[d.p.isin(self.cfg.test_tolerances)]
        agg = dict(overrun_over_p=("overrun_over_p", "max"), max_consec=("max_consec", "max"),
                   **{f"mk_worst_k{k}": (f"mk_worst_k{k}", "min") for k in self.cfg.k_list})
        if with_over_budget:
            agg["over_budget_pct"] = ("over_budget", lambda v: v.mean() * 100)
        return d.groupby(["scenario", "route", "p"]).agg(**agg)

    def checks(self, summary, name):
        return [check(f"{name}: {s} {r} meets p", bool((g.overrun_over_p <= 1).all()), f"worst overrun rate / p = {g.overrun_over_p.max():.2f}")
                for (s, r), g in summary.reset_index().groupby(["scenario", "route"])]


class HeldOutReplay:
    """Each budget replayed on traces that were not used to derive it: the extra baselines (baseline2 when there are none).
    Reports overrun rate / p, the longest burst of overruns, the worst-case (m, k) and the over-budget against the oracle budget
    (the (1-p) quantile of the held-out trace)."""

    def __init__(self, cfg, replay):
        self.cfg, self.replay = cfg, replay

    def run(self, scenarios, dep):
        rows, notes = [], []
        for s in scenarios:
            held = s.ids("extra_baseline")
            if not held:
                held = ["baseline2"]
                notes.append(f"{s.name}: no extra baselines, the replay uses baseline2, which is part of the profiling (not independent)")
            for run_id in held:
                for inst in s.instances:
                    x = s.series(run_id, inst)
                    for d in dep[dep.scenario == s.name].itertuples():
                        rows.append(dict(scenario=s.name, route=d.route, p=d.p, held_out=run_id, over_budget=d.Q_ms / np.quantile(x, 1 - d.p) - 1,
                                         **self.replay.run(x, d.Q_ms, d.p)))
        table = self.replay.summarise(rows, True)
        return table, self.replay.checks(table, "held-out"), notes


class BurstCheck:
    """Each budget replayed on the stressed profiling traces: the structure of the overruns (bursts, (m, k)), not the calibration:
    these traces are the profiling data."""

    def __init__(self, cfg, replay):
        self.cfg, self.replay = cfg, replay

    def run(self, scenarios, dep):
        rows = []
        for s in scenarios:
            for run_id in s.ids("stress"):
                for inst in s.instances:
                    x = s.series(run_id, inst)
                    for d in dep[dep.scenario == s.name].itertuples():
                        rows.append(dict(scenario=s.name, route=d.route, p=d.p, **self.replay.run(x, d.Q_ms, d.p)))
        table = self.replay.summarise(rows, False)
        return table, []


class BoundCheck:
    """The bound C_p of the first baseline applied to the second baseline (cluster-aware exceedance test). A failure without any
    change of the platform shows that the bound drifts between runs, which is what alpha_drift covers."""

    def __init__(self, cfg, bound):
        self.cfg, self.bound = cfg, bound

    def run(self, scenarios, bounds):
        ucb = bounds.set_index(["scenario", "run", "instance", "p"]).ucb
        rows = []
        for s in scenarios:
            for inst in s.instances:
                x = s.series("baseline2", inst)
                for p in self.cfg.tolerances:
                    C = ucb[(s.name, "baseline1", inst, p)]
                    rows.append(dict(scenario=s.name, instance=inst, p=p, bound=C, **self.bound.exceed_test(x, C, p)))
        t = pd.DataFrame(rows)
        t["passed"] = t.p_value > 0.05
        n_fail = int((~t.passed).sum())
        return t.set_index(["scenario", "instance", "p"]), [check("C_p of baseline1 holds on baseline2 without inflation", None,
                                                                   f"{len(t) - n_fail} of {len(t)} pass; failures show the bound drifts between runs, which alpha_drift covers")]


class LeaveOneOut:
    """alpha_drift derived from all the other baseline runs, applied to the bound of baseline1 and tested on the held-out run."""

    def __init__(self, cfg, bound):
        self.cfg, self.bound = cfg, bound

    def run(self, scenarios, bounds):
        ucb = bounds.set_index(["scenario", "run", "instance", "p"]).ucb
        rows, checks = [], []
        for s in scenarios:
            base = s.ids("baseline", "extra_baseline")
            if len(base) < 3:
                checks.append(check(f"leave-one-out of alpha_drift ({s.name})", None, f"needs at least 3 baseline runs, has {len(base)}"))
                continue
            for run_id in [r for r in base if r != "baseline1"]:
                others = [r for r in base if r != run_id]
                for inst in s.instances:
                    for p in self.cfg.test_tolerances:
                        v = [ucb[(s.name, r, inst, p)] for r in others]
                        alpha = max(v) / min(v)
                        C = ucb[(s.name, "baseline1", inst, p)] * alpha
                        rows.append(dict(scenario=s.name, run=run_id, instance=inst, p=p, alpha_loo=alpha, **self.bound.exceed_test(s.series(run_id, inst), C, p)))
        if not rows:
            return None, checks
        t = pd.DataFrame(rows)
        t["passed"] = t.p_value > 0.05
        for s_name, g in t.groupby("scenario"):
            checks.append(check(f"leave-one-out of alpha_drift ({s_name})", bool(g.passed.all()), f"{int(g.passed.sum())} of {len(g)} pass"))
        worst = t.sort_values("p_value").groupby(["scenario", "run", "p"]).head(1).sort_values(["scenario", "run", "p"])
        return worst.set_index(["scenario", "run", "p"]), checks


class StressRunCheck:
    """The budgets, derived from the profiling only, against the bound measured on the extra stressed run: the budget must not be
    lower than the measured bound, and the exceedance test of the budget on that run must pass."""

    def __init__(self, cfg, bound):
        self.cfg, self.bound = cfg, bound

    def run(self, scenarios, per_instance, bounds):
        ucb = bounds.set_index(["scenario", "run", "instance", "p"]).ucb
        rows = []
        for s in scenarios:
            if "stress_run" not in s.runs:
                continue
            for d in per_instance[(per_instance.scenario == s.name) & per_instance.p.isin(self.cfg.test_tolerances)].itertuples():
                measured = ucb[(s.name, "stress_run", d.instance, d.p)]
                rows.append(dict(scenario=s.name, route=d.route, p=d.p, covers=d.Q_ms >= measured, b_over_m=d.Q_ms / measured,
                                 passed=self.bound.exceed_test(s.series("stress_run", d.instance), d.Q_ms, d.p)["p_value"] > 0.05))
        if not rows:
            return None, [check("budgets against the extra stressed run", None, "no stressed run given")]
        t = pd.DataFrame(rows)
        v = t.groupby(["scenario", "route"]).agg(covers_measured_bound=("covers", "all"), exceedance_test=("passed", "all"))
        v["pass"] = v.all(axis=1)
        for p in self.cfg.test_tolerances:
            v[f"budget/measured p={p:g}"] = t[t.p == p].groupby(["scenario", "route"]).b_over_m.min()
        return v, [check(f"{s} {r} covers the extra stressed run", bool(row["pass"]), f"min budget/measured = {t[(t.scenario == s) & (t.route == r)].b_over_m.min():.3f}")
                   for (s, r), row in v.iterrows()]
