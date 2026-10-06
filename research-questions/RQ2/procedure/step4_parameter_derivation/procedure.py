"""The procedure from profiling data to budgets: Procedure runs the entities in order and reports each step."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config import ROLES
from data import Scenario
from EVT import TailEstimator, BoundEstimator, EVT
from inflationFactors import AlphaDrift, AlphaCores, PlatformFactor, InflationFactors
from parameterDerivation import ParameterDerivation
from offlineValidation import Replay, HeldOutReplay, BurstCheck, BoundCheck, LeaveOneOut, StressRunCheck
from dataValidity import DataSummary, PFloor, PlatformEvents, NoiseFloorCheck
from riskCurve import RiskCurve
from report import Report, check


@dataclass
class Results:
    """What a practitioner can use after run(): the budgets, the factors, the bounds and the validity summary."""
    scenarios: list
    bounds: pd.DataFrame
    factors: InflationFactors
    budgets: pd.DataFrame                 # deployment budget per scenario, route, p
    budgets_per_instance: pd.DataFrame
    validity: pd.DataFrame
    tables: dict = field(default_factory=dict)


class Procedure:
    def __init__(self, cfg):
        self.cfg = cfg
        self.report = Report(cfg.out_dir, cfg.show_figures)
        self.tail = TailEstimator(cfg)
        self.bound = BoundEstimator(cfg, self.tail)
        self.evt = EVT(cfg, self.tail, self.bound)

    def run(self):
        cfg, r, tables = self.cfg, self.report, {}

        r.step("1/6  Loading the data")
        scenarios = [Scenario(spec, cfg.period_ms) for spec in cfg.scenarios]
        for s in scenarios:
            print(f"{s.name}: {len(s.instances)} instance(s), {len(s.runs)} runs ({', '.join(s.runs)}), period T = {s.period_ms:.3f} ms, m = {s.m}")

        r.step("2/6  Are the data usable?  (runs, p_floor, platform events, noise floor)")
        tables["data_summary"], checks = DataSummary().run(scenarios)
        r.table("data_summary", tables["data_summary"], "jobs, skipped, late and C (ms) per run")
        r.add_checks(checks)
        tables["p_floor"], checks = PFloor(cfg, self.bound).run(scenarios)
        r.table("p_floor", tables["p_floor"], "stalls and late jobs that no budget removes", sci=("event rate", "95% upper", "bad-job rate"))
        r.add_checks(checks)
        noise = None if cfg.noise_floor is None else (cfg.noise_floor if isinstance(cfg.noise_floor, pd.DataFrame) else pd.read_csv(cfg.noise_floor))
        t, checks = NoiseFloorCheck().run(scenarios, noise)
        r.add_checks(checks)
        if t is not None:
            tables["noise_floor"] = t
            r.table("noise_floor", t, "step 1: the runtime's own overhead and dispatch latency against the task")
        pe = PlatformEvents(cfg, self.tail)
        for s in scenarios:
            t, checks = pe.run(s)
            r.add_checks(checks)
            if t is not None:
                tables[f"platform_events_{s.name}"] = t
                r.table(f"platform_events_{s.name}", t, f"{s.name}: coincident extremes across instances, GEV shape xi with and without them")

        r.step("3/6  Tail estimation: bounds C_p")
        longs, wides = zip(*[self.evt.bounds(s) for s in scenarios])
        bounds, wide = pd.concat(longs, ignore_index=True), pd.concat(wides, ignore_index=True).set_index(["scenario", "run", "instance"])
        tables["bounds"] = wide
        r.table("bounds", wide, f"C_p (ms) per run and tolerance (upper bound), GEV bound at p={cfg.p_gev:g}, theta, xi, Gumbel test p-value")
        for s in scenarios:
            r.figure(f"evt_fit_{s.name}", self.evt.figure(s, ROLES))
        prof = wide[wide.index.get_level_values("run").isin(ROLES)]
        both = bounds[bounds.gev.notna()]
        r.add_checks([check("tail bounded (xi < 0) in the profiling runs", None, f"xi < 0 in {int((prof.xi < 0).sum())} of {len(prof)} fits"),
                      check("GEV and empirical bound agree at p=%g" % cfg.p_gev, None,
                            f"largest difference {100 * np.abs(both.gev / both.ucb - 1).max():.1f}% over {len(both)} runs and instances")])

        r.step("4/6  Inflation factors")
        drift, cores = AlphaDrift(bounds), AlphaCores(bounds)
        platform = PlatformFactor(cfg.platform_table, cfg.platform_factors)
        factors = InflationFactors(drift, cores, platform)
        tables["inflation_factors"] = factors.table(scenarios)
        r.table("inflation_factors", tables["inflation_factors"], "alpha_drift (spread of the baseline bounds), alpha_cores (stress / baseline bound of the task), alpha_platform(m)")
        if platform.table is not None:
            r.table("platform_factor", platform.table, "step 1: median of the victim with m enemy cores / median alone")
        tables["alpha_cores_profiling"] = cores.profiling
        r.table("alpha_cores_profiling", cores.profiling, "C_p of the baseline and the stress runs of the profiling, and their ratio")
        for s in scenarios:
            r.add_checks([check(f"alpha_drift has at least 3 baseline runs ({s.name})", int(drift.n_runs[s.name]) >= 3,
                                f"{int(drift.n_runs[s.name])} baseline runs; with fewer the spread is coarse")])
        stress_tables, m_rows = [], []
        for s in scenarios:
            t, row = cores.on_stress_run(s, self.bound, list(cfg.tolerances))
            if t is not None:
                stress_tables.append(t)
                m_rows.append(row)
                a = platform.value(s.m)
                r.add_checks([check(f"m rule ({s.name}): the task is less sensitive than the platform factor of m={s.m}",
                                    None if a is None else bool(row["task_upper_ci"] < a),
                                    f"task stress ratio up to {row['task_upper_ci']:.3f} against factor {'n/a' if a is None else f'{a:.3f}'}")])
            elif "stress_run" in s.runs:
                r.note(f"{s.name}: no stress_baseline given, so alpha_cores on the stressed run and the rule for m are skipped")
        if stress_tables:
            tables["alpha_cores_stress_run"] = pd.concat(stress_tables).set_index(["scenario", "p"])
            r.table("alpha_cores_stress_run", tables["alpha_cores_stress_run"], "the stress ratio measured on the extra stressed run (with its paired baseline)")

        r.step("5/6  Budgets of the three routes")
        derivation = ParameterDerivation(cfg, factors)
        per_instance, dep = derivation.derive(scenarios)
        for n in derivation.notes:
            r.note(n)
        tables["budgets"] = dep
        r.table("budgets", dep.set_index(["scenario", "route", "p"]), show=False)
        r.table("budgets_per_instance", per_instance.set_index(["scenario", "route", "instance", "p"]), show=False)
        r.table("budgets_summary", derivation.results_table(dep),
                "budget Q in ms (Q / T) per route and tolerance; admitted = Q / T within the admission limit; HWM is one budget for every p")

        r.step("6/6  Offline validation")
        replay = Replay(cfg)
        for name, run, title in (
                ("bound_check", lambda: BoundCheck(cfg, self.bound).run(scenarios, bounds), "C_p of baseline1 applied to baseline2 (cluster-aware exceedance test)"),
                ("held_out_replay", lambda: HeldOutReplay(cfg, replay).run(scenarios, dep)[:2], "budgets replayed on held-out traces (miss rate / p <= 1 meets p)"),
                ("burst_check", lambda: BurstCheck(cfg, replay).run(scenarios, dep), "budgets replayed on the stressed profiling traces: bursts of misses"),
                ("leave_one_out", lambda: LeaveOneOut(cfg, self.bound).run(scenarios, bounds), "alpha_drift from the other baselines, tested on the held-out one (worst instance)"),
                ("stress_run_check", lambda: StressRunCheck(cfg, self.bound).run(scenarios, per_instance, bounds), "budgets against the bound measured on the extra stressed run")):
            t, checks = run()
            r.add_checks(checks)
            if t is not None:
                tables[name] = t
                r.table(name, t, title)
        for s in scenarios:
            if not s.ids("extra_baseline"):
                r.note(f"{s.name}: no extra baselines, the held-out replay uses baseline2, which is part of the profiling")
            curve = RiskCurve(cfg, s, factors)
            r.figure(f"risk_curve_{s.name}", curve.figure(dep))
            r.table(f"budgets_other_tolerances_{s.name}", curve.table(), show=False)

        validity = r.summary()
        return Results(scenarios, bounds, factors, dep, per_instance, validity, tables)
