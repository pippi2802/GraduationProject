"""Tail estimation: TailEstimator (GEV, extremal index), BoundEstimator (bootstrap bounds C_p) and EVT (the per-scenario pipeline)."""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import genextreme, gumbel_r, chi2, binom, beta


class TailEstimator:
    """Block maxima and the GEV: shape xi, upper end, extremal index theta, and the GEV bound of the per-job (1-p) level."""

    def __init__(self, cfg):
        self.cfg = cfg

    def block_maxima(self, x, b=None):
        b = b or self.cfg.block
        k = len(x) // b
        return x[: k * b].reshape(k, b).max(axis=1)

    def fit(self, maxima):
        c, loc, scale = genextreme.fit(maxima)                       # scipy's c = -xi
        return dict(xi=-c, loc=loc, scale=scale, upper_end=loc + scale / c if c > 0 else np.nan)

    def extremal_index(self, x, p, r=None):
        """runs estimator: clusters of exceedances of the (1-p) quantile / exceedances"""
        r = r or self.cfg.runs_r
        idx = np.flatnonzero(x > np.quantile(x, 1 - p))
        return (1 + np.sum(np.diff(idx) > r)) / len(idx) if len(idx) else np.nan

    def gev_bound(self, x, p, theta):
        """GEV bound from block maxima with the extremal index, the shape xi, and the likelihood-ratio test Gumbel vs GEV"""
        b = self.cfg.block
        mx = self.block_maxima(x, b)
        c, loc, scale = genextreme.fit(mx)
        bound = genextreme.ppf((1 - p) ** (b * theta), c, loc, scale)
        lg, sg = gumbel_r.fit(mx)
        lr = 2 * (genextreme.logpdf(mx, c, loc, scale).sum() - gumbel_r.logpdf(mx, lg, sg).sum())
        return bound, -c, chi2.sf(lr, 1)


class BoundEstimator:
    """The bound C_p of a trace: the (1-p) quantile with an upper confidence bound from a moving-block bootstrap
    (blocks of l_boot jobs keep the temporal dependence). Also the cluster-aware exceedance test of a bound."""

    def __init__(self, cfg, tail):
        self.cfg, self.tail = cfg, tail
        self.rng = np.random.default_rng(0)

    def boot_dist(self, x, ps, L=None):
        """bootstrap distribution of the (1-p) quantiles, shape (n_boot, len(ps))"""
        L = L or self.cfg.l_boot
        qs, n = 1 - np.asarray(ps), len(x)
        k, ar = n // L, np.arange(L)
        out = np.empty((self.cfg.n_boot, len(ps)))
        for i in range(self.cfg.n_boot):
            starts = self.rng.integers(0, n - L + 1, size=k)
            out[i] = np.quantile(x[(starts[:, None] + ar).ravel()], qs)
        return out

    def empirical(self, x, ps, L=None):
        """point (1-p) quantiles and their upper confidence bounds"""
        return np.quantile(x, 1 - np.asarray(ps)), np.quantile(self.boot_dist(x, ps, L), 1 - self.cfg.alpha, axis=0)

    def exceed_test(self, x, C, p):
        """is C a valid (1-p) bound for x? exceedances, clusters of them, the clusters expected at p, and the p-value"""
        pos = np.flatnonzero(x > C)
        kc = (1 + int(np.sum(np.diff(pos) > self.cfg.runs_r))) if len(pos) else 0
        n_eff = max(int(round(len(x) * self.tail.extremal_index(x, p))), 1)
        return dict(exceed=len(pos), clusters=kc, expected_clusters=n_eff * p, p_value=binom.sf(kc - 1, n_eff, p) if kc else 1.0)

    @staticmethod
    def cp_upper(k, n, conf=0.95):
        """one-sided Clopper-Pearson upper bound for k events in n trials"""
        if n == 0:
            return np.nan
        return 1 - (1 - conf) ** (1 / n) if k == 0 else beta.ppf(conf, k + 1, n - k)


class EVT:
    """The tail estimation of one scenario: a bound C_p for every run, instance and tolerance (empirical and GEV), the GEV
    summary (xi, theta, likelihood-ratio test) and the fit diagnostics."""

    def __init__(self, cfg, tail, bound):
        self.cfg, self.tail, self.bound = cfg, tail, bound

    def bounds(self, scenario):
        """(long table: one row per run, instance, p; wide table: the same with the GEV summary)"""
        ps, cfg, long, wide = list(self.cfg.tolerances), self.cfg, [], []
        for run_id, (run, kind) in scenario.runs.items():
            for inst in scenario.instances:
                x = run.C(inst)
                point, ucb = self.bound.empirical(x, ps)
                theta = self.tail.extremal_index(x, cfg.p_gev)
                gev, xi, lrt = self.tail.gev_bound(x, cfg.p_gev, theta)
                ucb2 = self.bound.empirical(x, [cfg.p_gev], L=2 * cfg.l_boot)[1][0]
                for k, p in enumerate(ps):
                    long.append(dict(scenario=scenario.name, run=run_id, kind=kind, instance=inst, p=p, n=len(x), emp=point[k], ucb=ucb[k],
                                     gev=gev if p == cfg.p_gev else np.nan))
                wide.append(dict(scenario=scenario.name, run=run_id, instance=inst, **{f"C_{p:g}": ucb[k] for k, p in enumerate(ps)},
                                 GEV=gev, theta=theta, xi=xi, LRT_p=lrt, **{f"C_{cfg.p_gev:g} (2L)": ucb2}))
        return pd.DataFrame(long), pd.DataFrame(wide)

    def figure(self, scenario, roles):
        """per profiling run (instances pooled): histogram of the block maxima with the fitted pdf, QQ plot, return level"""
        fig, ax = plt.subplots(3, len(roles), figsize=(3.4 * len(roles), 8.5), squeeze=False)
        for j, role in enumerate(roles):
            x = np.concatenate([self.tail.block_maxima(scenario.series(role, i)) for i in scenario.instances])
            c, loc, scale = genextreme.fit(x)
            xs = np.sort(x)
            pr = np.arange(1, len(xs) + 1) / (len(xs) + 1)
            grid = np.linspace(xs.min() - 0.1 * np.ptp(xs), xs.max() + 0.1 * np.ptp(xs), 300)
            ax[0, j].hist(x, bins="auto", density=True, alpha=.4)
            ax[0, j].plot(grid, genextreme.pdf(grid, c, loc, scale), "r-")
            ax[0, j].set_title(f"{scenario.name} / {role}\nxi = {-c:.2f}", fontsize=9)
            q = genextreme.ppf(pr, c, loc, scale)
            ax[1, j].scatter(q, xs, s=8)
            ax[1, j].plot([q.min(), q.max()], [q.min(), q.max()], "r--")
            T = np.logspace(0.05, 3, 100)
            ax[2, j].semilogx(T, genextreme.isf(1 / T, c, loc, scale), "r-")
            ax[2, j].scatter(1 / (1 - pr), xs, s=8)
        for r, lab in enumerate(["pdf of the block maxima", "QQ: model quantile (x) / observed (y), ms", "return level, ms"]):
            ax[r, 0].set_ylabel(lab)
        fig.tight_layout()
        return fig
