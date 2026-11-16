#!/usr/bin/env python3
"""PLATFORM EFFECTS - separating configuration effects from round (platform/time) effects. Rerun data only; computed and reported, not interpreted.

Writes output/platform/: platform_run_metrics.csv (step 1), platform_friedman_decomp.csv (2a, 2b), platform_within_round_diffs.csv (2c),
platform_table_<placement>.tex (step 4).

Definitions, fixed in advance:
  Metrics per run (all jobs of the run unless stated): miss_skip_pct (lost releases / releases, skips from gaps in release_us);
  dispatch_p99_us (p99 of dispatch_latency_us, jobs with C > Q excluded, Q = U*P); cv_C_pct (100 * sample std / mean of C);
  interrupted_jobs_pct (100 * share of jobs with mid_job_preempt_us > 10 us); switched_jobs_pct (100 * share of jobs with nonvol_ctxt >= 1).
  Grid per placement x P x U x metric: configurations x 4 rounds (9 configurations; 7 at U = 0.94, where isolcpus removed and all defaults were not run).
  2a Friedman statistic with tie correction. Test for configuration: blocks = rounds (n = 4), treatments = configurations. Test for round: blocks =
     configurations, treatments = the 4 rounds. p = Monte Carlo permutation p-value of the statistic (labels permuted within every block, 100000
     permutations, p = (1 + #{T_perm >= T_obs}) / (1 + 100000), seed 20261104); the asymptotic chi-square p is written alongside (poor with 4 blocks).
     Holm within placement and metric, separately for the two tests, over the 8 cells (P x U).
  2b y = log(value + c), c = 0.5 * the smallest positive value of the metric over all 544 runs; additive model configuration + round, no interaction
     (balanced grid); shares = SS_configuration / SS_total, SS_round / SS_total, residual.
  2c per configuration: the four within-round differences (configuration minus full isolation, same round, absolute units); same_sign = max(#positive, #negative).
"""
import sys

import numpy as np
import pandas as pd

import common as cm

OUTP = cm.OUT / "platform"
METRICS = [("miss_skip_pct", "Miss+skip rate [%]"), ("dispatch_p99_us", "Dispatch latency p99 [$\\mu$s]"), ("cv_C_pct", "CV of $C$ [%]"),
           ("interrupted_jobs_pct", "Jobs with mid-job preemption $>10\\,\\mu$s [%]"), ("switched_jobs_pct", "Jobs with $\\geq 1$ involuntary switch [%]")]
MNAMES = [m for m, _ in METRICS]
CELLS = [(s, u) for s, _, _ in cm.SCALES for u in cm.UTILS]


def run_table():
    runs, _ = cm.get_runs()
    rows = []
    for (pl, c, s, u, r), a in runs.items():
        P = cm.PERIOD[s]
        Q = u * P
        C = a["C_cputime_us"]
        seq, skipped = cm.lost_sequence(a, P)
        n = len(C)
        keep = C <= Q
        rows.append(dict(placement=pl, configuration=c, scale=s, U=u, round=r, n_jobs=n,
                         miss_skip_pct=100.0 * (int(a["deadline_miss"].sum()) + skipped) / (n + skipped),
                         dispatch_p99_us=float(np.percentile(a["dispatch_latency_us"][keep], 99)) if keep.any() else np.nan,
                         cv_C_pct=100.0 * float(np.std(C, ddof=1) / np.mean(C)),
                         interrupted_jobs_pct=100.0 * float((a["mid_job_preempt_us"] > cm.INTERRUPT_US).mean()),
                         switched_jobs_pct=100.0 * float((a["nonvol_ctxt"] >= 1).mean())))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- statistics
def midranks(v):
    u, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
    cs = np.cumsum(cnt)
    return (((cs - cnt + 1) + cs) / 2.0)[inv]


def chi2_sf(x, df):
    """upper tail of the chi-square distribution (regularized upper incomplete gamma Q(df/2, x/2)), series / continued fraction"""
    if x <= 0:
        return 1.0
    a, z = df / 2.0, x / 2.0
    from math import lgamma, exp, log
    if z < a + 1:
        s, term, n = 1.0 / a, 1.0 / a, 1
        while abs(term) > 1e-14 * abs(s) and n < 1000:
            term *= z / (a + n)
            s += term
            n += 1
        return 1.0 - s * exp(-z + a * log(z) - lgamma(a))
    b = z + 1 - a
    c = 1e300
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        dl = d * c
        h *= dl
        if abs(dl - 1) < 1e-14:
            break
    return exp(-z + a * log(z) - lgamma(a)) * h


def friedman(V, rng):
    """V: blocks x treatments. tie-corrected Friedman statistic, permutation p (within blocks) and asymptotic p"""
    n, k = V.shape
    R = np.vstack([midranks(row) for row in V])
    den = (R ** 2).sum() - n * k * (k + 1) ** 2 / 4.0
    if den <= 1e-12:
        return 0.0, 1.0, 1.0
    num = lambda S: (k - 1) * ((S ** 2).sum(axis=-1) - n * n * k * (k + 1) ** 2 / 4.0)
    T_obs = float(num(R.sum(axis=0)) / den)
    idx = rng.random((cm.N_PERM, n, k)).argsort(axis=2)
    Rp = np.take_along_axis(np.broadcast_to(R, (cm.N_PERM, n, k)), idx, axis=2)
    T = num(Rp.sum(axis=1)) / den
    return T_obs, (1 + int((T >= T_obs - 1e-9).sum())) / (1 + cm.N_PERM), chi2_sf(T_obs, k - 1)


def decomposition(M, c):
    """M: configurations x rounds, values; shares of the SS of log(M + c)"""
    y = np.log(M + c)
    g = y.mean()
    tot = ((y - g) ** 2).sum()
    cfg = y.shape[1] * ((y.mean(axis=1) - g) ** 2).sum()
    rnd = y.shape[0] * ((y.mean(axis=0) - g) ** 2).sum()
    return (cfg / tot, rnd / tot, (tot - cfg - rnd) / tot) if tot > 0 else (np.nan, np.nan, np.nan)


def main():
    OUTP.mkdir(parents=True, exist_ok=True)
    t = run_table()
    t.to_csv(OUTP / "platform_run_metrics.csv", index=False)
    const = {m: 0.5 * float(t[m][t[m] > 0].min()) for m in MNAMES}
    rng = np.random.default_rng(cm.SEED)
    rows, diffs = [], []
    for pl in cm.PLACE_NAMES:
        for m in MNAMES:
            for s, u in CELLS:
                configs = [c for c in cm.CONFIGS if cm.planned(c, u)]
                M = np.array([[t[(t.placement == pl) & (t.configuration == c) & (t.scale == s) & (t.U == u) & (t["round"] == r)][m].iloc[0]
                               for r in cm.ROUNDS] for c in configs])
                Tc, pc, pc_as = friedman(M.T, rng)               # configuration effect, rounds as blocks
                Tr, pr, pr_as = friedman(M, rng)                 # round effect, configurations as blocks
                sc, sr, se = decomposition(M, const[m])
                rows.append(dict(placement=pl, metric=m, scale=s, U=u, n_configs=len(configs), const=const[m],
                                 friedman_cfg_T=Tc, p_cfg_perm=pc, p_cfg_asym=pc_as, friedman_round_T=Tr, p_round_perm=pr, p_round_asym=pr_as,
                                 share_configuration=sc, share_round=sr, share_residual=se))
                fi = M[configs.index(cm.FULL)]
                for i, c in enumerate(configs):
                    if c == cm.FULL:
                        continue
                    d = M[i] - fi
                    npos, nneg = int((d > 0).sum()), int((d < 0).sum())
                    diffs.append(dict(placement=pl, metric=m, scale=s, U=u, configuration=c, **{f"diff_round{r}": d[j] for j, r in enumerate(cm.ROUNDS)},
                                      n_positive=npos, n_negative=nneg, n_zero=int((d == 0).sum()), same_sign=max(npos, nneg)))
    f = pd.DataFrame(rows)
    f["p_cfg_holm"] = np.nan
    f["p_round_holm"] = np.nan
    for (pl, m), g in f.groupby(["placement", "metric"]):
        f.loc[g.index, "p_cfg_holm"] = cm.holm(g.p_cfg_perm.to_numpy())
        f.loc[g.index, "p_round_holm"] = cm.holm(g.p_round_perm.to_numpy())
    f.to_csv(OUTP / "platform_friedman_decomp.csv", index=False)
    pd.DataFrame(diffs).to_csv(OUTP / "platform_within_round_diffs.csv", index=False)

    fmtp = lambda p: "<0.0001" if p < 1e-4 else f"{p:.4f}"
    for pl in cm.PLACE_NAMES:
        L = [r"\begin{table}[ht]", r"\centering", r"\scriptsize", r"\begin{tabular}{ll|rrr|rr}", r"\toprule",
             r"Metric & Cell & \multicolumn{3}{c|}{Share of the sum of squares} & \multicolumn{2}{c}{Friedman $p_{\mathrm{Holm}}$} \\",
             r" & period, $U$ & configuration & round & residual & configuration & round \\", r"\midrule"]
        for mi, (m, name) in enumerate(METRICS):
            if mi:
                L.append(r"\midrule")
            sub = f[(f.placement == pl) & (f.metric == m)]
            for j, (s, u) in enumerate(CELLS):
                r = sub[(sub.scale == s) & (sub.U == u)].iloc[0]
                first = rf"\multirow[t]{{{len(CELLS)}}}{{*}}{{{name}}}" if j == 0 else ""
                L.append(f"{first} & {s}, {u:g} & {r.share_configuration:.2f} & {r.share_round:.2f} & {r.share_residual:.2f} & {fmtp(r.p_cfg_holm)} & {fmtp(r.p_round_holm)} \\\\")
        L += [r"\bottomrule", r"\end{tabular}",
              r"\caption{Configuration and round effects, " + pl + r". Share of the total sum of squares of $\log(\text{value}+c)$ explained by configuration, by round, and left over "
              r"(additive model, no interaction; 9 configurations $\times$ 4 rounds, 7 configurations at $U=0.94$). Friedman test for configuration (rounds as blocks) and for round "
              r"(configurations as blocks): permutation $p$ (100\,000 permutations), Holm-adjusted within placement and metric over the eight cells.}",
              r"\label{tab:rq1-rerun-platform-" + pl + r"}", r"\end{table}"]
        (OUTP / f"platform_table_{pl}.tex").write_text("\n".join(L) + "\n")
    print(f"platform effects: {len(t)} runs, {len(f)} grids ({len(MNAMES)} metrics), {len(diffs)} configuration rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
