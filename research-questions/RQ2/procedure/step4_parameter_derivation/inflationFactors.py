"""The inflation factors: AlphaDrift, AlphaCores, PlatformFactor, and InflationFactors, which holds them together."""
import numpy as np
import pandas as pd


class AlphaDrift:
    """Variability of the bound between runs: the spread (max / min) of the baseline bounds over all baseline runs
    (the profiling baselines and the extra baselines), per instance and p. One value per scenario and p: the worst instance."""

    def __init__(self, bounds):
        b = bounds[bounds.kind.isin(["baseline", "extra_baseline"])]
        spread = b.groupby(["scenario", "instance", "p"]).ucb.agg(lambda v: v.max() / v.min())
        self.per_p = spread.groupby(["scenario", "p"]).max()
        self.n_runs = b.groupby("scenario").run.nunique()

    def value(self, scenario, p):
        return float(self.per_p[(scenario, p)])

    def at(self, scenario, p):
        """interpolated in log p between the computed tolerances (used by the risk curve)"""
        a = self.per_p[scenario].sort_index()
        return float(np.exp(np.interp(np.log(p), np.log(a.index.values), np.log(a.values))))

    def table(self):
        t = self.per_p.unstack("p")
        t["n_runs"] = self.n_runs
        return t


class AlphaCores:
    """Effect of the stress on the task's own bound: C_p of the stress runs / C_p of the baseline runs of the profiling
    (envelopes over the runs), per instance and p. With an extra stressed run and its paired baseline, the same ratio measured there
    (with a bootstrap interval) and the rule for m."""

    def __init__(self, bounds):
        env = lambda kind: bounds[bounds.kind == kind].groupby(["scenario", "instance", "p"])[["ucb", "gev"]].max()
        t = env("baseline").join(env("stress"), lsuffix="_base", rsuffix="_stress")
        t.columns = ["C_p_base", "C_p_base_GEV", "C_p_stress", "C_p_stress_GEV"]
        t["alpha_cores"] = t.C_p_stress / t.C_p_base
        self.profiling = t[["C_p_base", "C_p_stress", "C_p_base_GEV", "C_p_stress_GEV", "alpha_cores"]]
        self._ucb = bounds.set_index(["scenario", "run", "instance", "p"]).ucb

    def worst(self):
        """alpha_cores per scenario and p: the worst instance"""
        return self.profiling.alpha_cores.groupby(["scenario", "p"]).max()

    def on_stress_run(self, scenario, bound, tolerances):
        """(table per p, row for the m rule), or (None, None) when there is no stressed run with a paired baseline"""
        if "stress_run" not in scenario.runs or scenario.stress_baseline is None:
            return None, None
        rows = []
        for inst in scenario.instances:
            rat = bound.boot_dist(scenario.series("stress_run", inst), tolerances) / bound.boot_dist(scenario.series(scenario.stress_baseline, inst), tolerances)
            for k, p in enumerate(tolerances):
                s_t, b_t = self._ucb[(scenario.name, "stress_run", inst, p)], self._ucb[(scenario.name, scenario.stress_baseline, inst, p)]
                prof = self.profiling.loc[(scenario.name, inst, p)]
                lo, hi = np.percentile(rat[:, k], [2.5, 97.5])
                rows.append(dict(scenario=scenario.name, instance=inst, p=p, alpha_cores_profiling=prof.alpha_cores, alpha_cores_there=s_t / b_t,
                                 ci_lo=lo, ci_hi=hi, stress_over_drift=(s_t / prof.C_p_stress) / (b_t / prof.C_p_base)))
        t = pd.DataFrame(rows)
        by_p = t.groupby("p").agg(alpha_cores_profiling=("alpha_cores_profiling", "max"), alpha_cores_there=("alpha_cores_there", "max"),
                                  ci_lo=("ci_lo", "min"), ci_hi=("ci_hi", "max"), stress_over_drift=("stress_over_drift", "max"))
        by_p.insert(0, "scenario", scenario.name)
        return by_p.reset_index(), dict(scenario=scenario.name, task_alpha_cores=t.alpha_cores_there.max(), task_upper_ci=t.ci_hi.max())


class PlatformFactor:
    """alpha_platform(m): computed in step 1 as the median run time of the victim with m enemy cores over its median alone (the larger
    of the cache and the memory victim); read here from step 1's table. Explicit values {m: factor} take precedence."""

    def __init__(self, table=None, explicit=None):
        self.explicit = dict(explicit or {})
        self.table = None
        if table is not None:
            t = table if isinstance(table, pd.DataFrame) else pd.read_csv(table)
            self.table = t.set_index("m") if "m" in t.columns else t

    def value(self, m):
        if m in self.explicit:
            return float(self.explicit[m])
        if self.table is not None and m in self.table.index:
            return float(self.table.alpha_platform[m])
        return None


class InflationFactors:
    """All the factors of the procedure, ready for the routes."""

    def __init__(self, drift, cores, platform):
        self.drift, self.cores, self.platform = drift, cores, platform

    def table(self, scenarios):
        rows = []
        for s in scenarios:
            for p in self.drift.per_p[s.name].index:
                rows.append(dict(scenario=s.name, p=p, alpha_drift=self.drift.value(s.name, p), alpha_cores=self.cores.worst()[(s.name, p)],
                                 m=s.m, alpha_platform=self.platform.value(s.m)))
        return pd.DataFrame(rows).set_index(["scenario", "p"])
