#!/usr/bin/env python3
"""STEP 3 - tests against full isolation. Needs output/step1_runs.csv.

Per placement, configuration (not full isolation) and metric (miss_skip_pct, tail_spread):
  one-sided stratified Wilcoxon rank-sum permutation test. Strata = cells (scale x U) where both the configuration and full isolation have runs.
  In each stratum the runs of the configuration and of full isolation (4 + 4) are ranked together (mid-ranks for ties); T_obs = sum over strata of the
  rank sum of the configuration; the labels are permuted within every stratum independently (100000 permutations, one uniformly drawn labeling per
  stratum and permutation); p = (1 + #{T_perm >= T_obs}) / (1 + 100000), "worse" = larger value. Seed 20261104 (numpy default_rng), one generator
  used in a fixed test order. Holm within each placement and metric (family = the configurations of that placement).
  Hodges-Lehmann shift: median of all pairwise differences (configuration run minus full-isolation run) within strata, pooled over the strata
  (the estimate that belongs to the unweighted stratified rank-sum statistic). miss_skip_pct: difference in percentage points;
  tail_spread: factor = exp(median of log S_c - log S_FI).
Writes output/step3_tests.csv and output/step3_tests_<placement>.tex.
"""
import itertools

import numpy as np
import pandas as pd

import common as cm

METRICS = [("miss_skip_pct", "Miss+skip rate", "pp"), ("tail_spread", "Tail spread", "factor")]


def strata(t, pl, c, metric):
    """list of (x_config, y_fi) arrays, one pair per cell where both have runs"""
    out = []
    for s, _, _ in cm.SCALES:
        for u in cm.UTILS:
            x = t[(t.placement == pl) & (t.configuration == c) & (t.scale == s) & (t.U == u)][metric].to_numpy()
            y = t[(t.placement == pl) & (t.configuration == cm.FULL) & (t.scale == s) & (t.U == u)][metric].to_numpy()
            if len(x) and len(y):
                out.append((x, y))
    return out


def perm_test(st, rng):
    T_obs, pieces = 0.0, []
    for x, y in st:
        v = np.r_[x, y]
        r = pd.Series(v).rank(method="average").to_numpy()
        n1 = len(x)
        T_obs += r[:n1].sum()
        combos = np.array(list(itertools.combinations(range(len(v)), n1)))
        sums = r[combos].sum(axis=1)                          # rank sum of the configuration for every labeling of the stratum
        pieces.append(sums[rng.integers(0, len(sums), cm.N_PERM)])
    T = np.sum(pieces, axis=0)
    return T_obs, (1 + int((T >= T_obs - 1e-9).sum())) / (1 + cm.N_PERM)


def hl(st, metric):
    d = []
    for x, y in st:
        if metric == "tail_spread":
            d.append((np.log(x)[:, None] - np.log(y)[None, :]).ravel())
        else:
            d.append((x[:, None] - y[None, :]).ravel())
    m = float(np.median(np.concatenate(d)))
    return float(np.exp(m)) if metric == "tail_spread" else m


def main():
    t = pd.read_csv(cm.OUT / "step1_runs.csv")
    rng = np.random.default_rng(cm.SEED)
    rows = []
    for pl in cm.PLACE_NAMES:
        for metric, _, unit in METRICS:
            for c in cm.CONFIGS[1:]:
                st = strata(t, pl, c, metric)
                T_obs, p = perm_test(st, rng)
                rows.append(dict(placement=pl, configuration=c, metric=metric, n_strata=len(st), T_obs=T_obs, p=p, hl_shift=hl(st, metric), hl_unit=unit))
    r = pd.DataFrame(rows)
    r["p_holm"] = np.nan
    for (pl, metric), g in r.groupby(["placement", "metric"]):
        r.loc[g.index, "p_holm"] = cm.holm(g.p.to_numpy())
    r["significant_holm_0.05"] = r.p_holm < 0.05
    r.to_csv(cm.OUT / "step3_tests.csv", index=False)

    for pl, slug, title, *_ in cm.PLACEMENTS:
        sub = r[r.placement == pl]
        lines = [r"\begin{table}[ht]", r"\centering", r"\small", r"\begin{tabular}{l|rrr|rrr}", r"\toprule",
                 r" & \multicolumn{3}{c|}{Miss+skip rate} & \multicolumn{3}{c}{Tail spread} \\",
                 r"Configuration & $p$ & $p_{\mathrm{Holm}}$ & HL [pp] & $p$ & $p_{\mathrm{Holm}}$ & HL [factor] \\", r"\midrule"]
        for c in cm.CONFIGS[1:]:
            a = sub[(sub.configuration == c) & (sub.metric == "miss_skip_pct")].iloc[0]
            b = sub[(sub.configuration == c) & (sub.metric == "tail_spread")].iloc[0]
            f = lambda p: "<0.0001" if p < 1e-4 else f"{p:.4f}"
            lines.append(f"{cm.tex_name(c)} & {f(a.p)} & {f(a.p_holm)} & {a.hl_shift:+.3f} & {f(b.p)} & {f(b.p_holm)} & {b.hl_shift:.2f} \\\\")
        lines += [r"\bottomrule", r"\end{tabular}",
                  r"\caption{Tests against full isolation, " + pl + r". One-sided stratified Wilcoxon rank-sum permutation test (strata: cells; 100\,000 permutations), "
                  r"$p_{\mathrm{Holm}}$ within placement and metric. HL: Hodges--Lehmann shift (configuration minus full isolation; percentage points for the miss+skip rate, "
                  r"multiplicative factor for the tail spread), pooled over the cells with runs of both.}",
                  r"\label{tab:rq1-rerun-tests-" + pl + r"}", r"\end{table}"]
        (cm.OUT / f"step3_tests_{pl}.tex").write_text("\n".join(lines) + "\n")
    print(f"step 3: {len(r)} tests; p_holm < 0.05 in {int(r['significant_holm_0.05'].sum())}")
    return 0


if __name__ == "__main__":
    main()
