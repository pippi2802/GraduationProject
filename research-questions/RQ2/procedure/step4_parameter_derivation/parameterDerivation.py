"""The budget Q of the three routes, per scenario, instance and tolerance: Route (Route1, Route2b, HighWaterMark) and ParameterDerivation."""
import numpy as np
import pandas as pd


class Route:
    """A way to turn the bounds and the factors into a budget Q (ms) for one instance and tolerance."""
    name = ""

    def label(self, scenario):
        return self.name

    def available(self, scenario, factors):
        return True

    def budget(self, scenario, inst, p, factors):
        raise NotImplementedError


class Route1(Route):
    """Q = C_p of the stress runs x alpha_drift. Needs baseline and stress profiling of the task."""
    name = "Route 1"

    def budget(self, scenario, inst, p, factors):
        return factors.cores.profiling.loc[(scenario.name, inst, p), "C_p_stress"] * factors.drift.value(scenario.name, p)


class Route2b(Route):
    """Q = C_p of the baseline runs x alpha_platform(m) x alpha_drift. Needs only baselines of the task plus the platform factor."""
    name = "Route 2b"

    def label(self, scenario):
        return f"Route 2b (m={scenario.m})"

    def available(self, scenario, factors):
        return factors.platform.value(scenario.m) is not None

    def budget(self, scenario, inst, p, factors):
        return (factors.cores.profiling.loc[(scenario.name, inst, p), "C_p_base"] * factors.platform.value(scenario.m)
                * factors.drift.value(scenario.name, p))


class HighWaterMark(Route):
    """Q = largest C of the stress runs x alpha_drift / accounting margin; one budget for every p. Platform events stay in,
    stalls (C > 2 T) are left out."""
    name = "HWM"

    def __init__(self, cfg):
        self.cfg, self._max = cfg, {}

    def _high_water_mark(self, scenario, inst):
        if (scenario.name, inst) not in self._max:
            limit = 2 * scenario.period_ms
            xs = [scenario.series(r, inst) for r in scenario.ids("stress")]
            self._max[(scenario.name, inst)] = max(float(x[x <= limit].max()) for x in xs)
        return self._max[(scenario.name, inst)]

    def budget(self, scenario, inst, p, factors):
        return self._high_water_mark(scenario, inst) * factors.drift.value(scenario.name, self.cfg.hwm_p) / self.cfg.hwm_margin


class ParameterDerivation:
    """Applies every route to every scenario. A multi-instance scenario has one reservation, so its deployment budget is the
    maximum over the instances."""

    def __init__(self, cfg, factors):
        self.cfg, self.factors = cfg, factors
        self.routes = [Route1(), Route2b(), HighWaterMark(cfg)]
        self.notes = []

    def derive(self, scenarios):
        rows = []
        for s in scenarios:
            for route in self.routes:
                if not route.available(s, self.factors):
                    self.notes.append(f"{s.name}: {route.name} skipped, no platform factor for m={s.m} (give the victim data or platform_factors)")
                    continue
                for inst in s.instances:
                    for p in self.cfg.tolerances:
                        rows.append(dict(scenario=s.name, route=route.label(s), instance=inst, p=p, Q_ms=route.budget(s, inst, p, self.factors)))
        per_instance = pd.DataFrame(rows)
        dep = per_instance.groupby(["scenario", "route", "p"], as_index=False).Q_ms.max()
        period = {s.name: s.period_ms for s in scenarios}
        dep["Q_over_T"] = dep.Q_ms / dep.scenario.map(period)
        dep["runtime_us"] = np.ceil(dep.Q_ms * 1000).astype(int)               # the reservation, rounded up so it is never below Q
        dep["period_us"] = (dep.scenario.map(period) * 1000).round().astype(int)
        dep["admitted"] = dep.Q_over_T <= self.cfg.admission_max
        return per_instance, dep

    @staticmethod
    def results_table(dep):
        """one row per scenario and route, one column per tolerance: Q in ms (Q / T)"""
        d = dep.assign(cell=lambda x: x.Q_ms.round(2).astype(str) + " (" + x.Q_over_T.round(2).astype(str) + ")")
        t = d.pivot_table(index=["scenario", "route"], columns="p", values="cell", aggfunc="first")
        t["all admitted"] = d.groupby(["scenario", "route"]).admitted.all()
        return t
