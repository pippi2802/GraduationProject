"""The risk curve of a scenario: risk(Q | T), the per-job probability that C exceeds a budget Q, and its inverse, the budget for any tolerance."""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


class RiskCurve:
    """Drawn in p from the profiled traces (point estimates, no bootstrap margin) with the same factors as the routes, alpha_drift
    interpolated in log p. Routes: Route 1 (stress runs) and Route 2b (baseline runs x platform factor, when available)."""

    P_GRID = np.logspace(-4, np.log10(0.3), 60)

    def __init__(self, cfg, scenario, factors):
        self.cfg, self.s, self.f = cfg, scenario, factors
        self._curves = {}

    def _route(self, route):
        if route == "Route 1":
            return self.s.ids("stress"), 1.0
        a = self.f.platform.value(self.s.m)
        return (self.s.ids("baseline"), a) if a is not None else (None, None)

    def _q_point(self, run_ids, p):
        return max(np.quantile(self.s.series(r, i), 1 - p) for r in run_ids for i in self.s.instances)

    def curve(self, route):
        if route not in self._curves:
            run_ids, plat = self._route(route)
            if run_ids is None:
                return None
            self._curves[route] = np.array([self._q_point(run_ids, p) * plat * self.f.drift.at(self.s.name, p) for p in self.P_GRID])
        return self._curves[route]

    def budget_at(self, route, p):
        """budget Q (ms) for the tolerance p"""
        return float(np.exp(np.interp(np.log(p), np.log(self.P_GRID), np.log(self.curve(route)))))

    def risk_at(self, route, q_ms):
        """per-job overrun probability P(C > Q) of the budget Q (ms); the end values (1e-4, 0.3) outside the curve"""
        q = self.curve(route)
        o = np.argsort(q)
        return float(np.exp(np.interp(np.log(q_ms), np.log(q[o]), np.log(self.P_GRID[o]))))

    def table(self, ps=(0.1, 0.03, 0.01, 0.003, 0.001, 0.0003, 0.0001)):
        """budgets for other tolerances: Q in ms (Q / T)"""
        rows = {}
        for route in ("Route 1", "Route 2b"):
            if self.curve(route) is not None:
                rows[(self.s.name, route)] = {f"p={p:g}": f"{self.budget_at(route, p):.2f} ({self.budget_at(route, p) / self.s.period_ms:.2f})" for p in ps}
        return pd.DataFrame(rows).T

    def figure(self, dep):
        """risk against Q / T; the markers are the budgets of the table (with the bootstrap margin)"""
        fig, ax = plt.subplots(figsize=(6, 4.2))
        d = dep[dep.scenario == self.s.name]
        for route in ("Route 1", "Route 2b"):
            q = self.curve(route)
            if q is None:
                continue
            line, = ax.semilogy(q / self.s.period_ms, self.P_GRID, label=route)
            m = d[d.route.str.startswith(route)]
            ax.plot(m.Q_over_T, m.p, "o", color=line.get_color(), mec="k", ms=6)
        h = d[d.route == "HWM"]
        if len(h):
            ax.axvline(h.Q_over_T.iloc[0], color="k", ls="--", lw=1, label="HWM (no probability)")
        ax.axvline(self.cfg.admission_max, color="grey", ls=":", label=f"admission {self.cfg.admission_max}")
        ax.set(title=self.s.name, xlabel="Q / T", ylabel="risk(Q | T) = p")
        ax.legend(fontsize=8)
        fig.tight_layout()
        return fig
