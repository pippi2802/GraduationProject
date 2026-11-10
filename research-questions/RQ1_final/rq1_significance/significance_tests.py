#!/usr/bin/env python3
"""RQ1 significance: does a configuration differ from full isolation (FI) by more than run-to-run variability?

    python3 significance_tests.py

Read-only on the frozen data; writes only next to this script. See README.md for the exact procedure.
Data, configurations, cells and warm-up exclusion are those of ../os-experiments/results_final/make_results_final.py
(imported would run its plotting, so the few definitions needed are repeated here and must stay in step with it).
"""
import pathlib
import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
RQ1 = HERE.parent
OS_DATA = RQ1 / "os-experiments" / "analysis" / "data"
BASE_DATA = RQ1 / "kubedeadline-experiments" / "analysis" / "data"

FULL = "full isolation"
SCENARIOS = [("01", "isolcpus removed"), ("02", "nohz_full removed"), ("03", "rcu_nocbs removed"), ("04", "systemd containment removed"),
             ("05", "IRQ steering removed"), ("06", "boot-params bundle removed"), ("08", "frequency pinning removed")]
SMT = "SMT enabled"
PLACEMENTS = [("single-core", "model1", "model1"), ("multi-core", "model5", "model5-phys")]
SMT_FILE = "model5-smt"
SCALES = ["tight", "soft"]
UTILS = [0.1, 0.5, 0.7, 0.94]
N_DROP = 6
N_PERM = 100_000
SEED = 20261104
ALPHA = 0.05
METRICS = ["S", "M"]


def read(path):
    df = pd.read_csv(path, usecols=["job_index", "R_wall_us", "deadline_miss", "skipped_before", "round", "scale", "U"])
    return df[df.job_index >= N_DROP]


def runs_of(df, config, placement):
    """one row per run = per round of a cell: S = p99.9(R)/median(R) of the executed jobs, M = (misses + skipped) / (jobs + skipped) in percent.
    Same formulas as cell_numbers() of make_results_final.py, applied to one round instead of the pooled cell."""
    rows = []
    for (scale, u, rnd), g in df.groupby(["scale", "U", "round"]):
        if u not in UTILS:
            continue
        n, skipped, misses = len(g), int(g.skipped_before.sum()), int(g.deadline_miss.sum())
        r = g.R_wall_us.to_numpy()
        rows.append(dict(placement=placement, configuration=config, scale=scale, U=u, round=int(rnd), n_jobs=n, skipped=skipped, misses=misses,
                         S=float(np.percentile(r, 99.9) / np.median(r)), M=100.0 * (misses + skipped) / (n + skipped)))
    return rows


def load_runs():
    rows = []
    for placement, model, base_file in PLACEMENTS:
        sources = [(FULL, BASE_DATA / f"{base_file}.csv")] + [(name, OS_DATA / f"{code}-{model}.csv") for code, name in SCENARIOS]
        if placement == "multi-core":
            sources.append((SMT, BASE_DATA / f"{SMT_FILE}.csv"))
        for name, path in sources:
            rows += runs_of(read(path), name, placement)
    return pd.DataFrame(rows).sort_values(["placement", "configuration", "scale", "U", "round"]).reset_index(drop=True)


def midranks(x):
    return pd.Series(x).rank(method="average").to_numpy()


def perm_test(cells, rng):
    """cells: list of (values_c, values_fi). Returns T_obs and the one-sided p (c larger = worse); labels shuffled within each cell only."""
    ranks, n_c = [], []
    for vc, vf in cells:
        r = midranks(np.r_[vc, vf])
        ranks.append(r)
        n_c.append(len(vc))
    t_obs = sum(r[:k].sum() for r, k in zip(ranks, n_c))
    t_perm = np.zeros(N_PERM)
    for r, k in zip(ranks, n_c):
        keys = rng.random((N_PERM, len(r)))
        pick = np.argpartition(keys, k - 1, axis=1)[:, :k]
        t_perm += r[pick].sum(axis=1)
    p = (1 + int((t_perm >= t_obs - 1e-9).sum())) / (1 + N_PERM)
    return float(t_obs), p


def hodges_lehmann(vc, vf, metric):
    if metric == "S":
        d = np.log(np.asarray(vc)[:, None]) - np.log(np.asarray(vf)[None, :])
        return float(np.exp(np.median(d)))
    return float(np.median(np.asarray(vc)[:, None] - np.asarray(vf)[None, :]))


def holm(p):
    p = np.asarray(p)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for i, idx in enumerate(order):
        run = max(run, (m - i) * p[idx])
        adj[idx] = min(1.0, run)
    return adj


def main():
    runs = load_runs()
    runs.to_csv(HERE / "runs.csv", index=False, float_format="%.6g")

    # ---- run counts per configuration and cell, against FI
    counts = []
    for placement in runs.placement.unique():
        pr = runs[runs.placement == placement]
        for config in pr.configuration.unique():
            for scale in SCALES:
                for u in UTILS:
                    c = pr[(pr.configuration == config) & (pr.scale == scale) & (pr.U == u)]
                    f = pr[(pr.configuration == FULL) & (pr.scale == scale) & (pr.U == u)]
                    counts.append(dict(placement=placement, configuration=config, scale=scale, U=u, n_runs=len(c), rounds=" ".join(map(str, c["round"])),
                                       n_runs_FI=len(f), rounds_FI=" ".join(map(str, f["round"])),
                                       status=("not run" if len(c) == 0 else "FI missing" if len(f) == 0 else "equal" if len(c) == len(f) else "unequal")))
    counts = pd.DataFrame(counts)
    counts.to_csv(HERE / "run_counts.csv", index=False)
    counts[counts.status.isin(["unequal", "not run", "FI missing"]) & (counts.configuration != FULL)].to_csv(HERE / "cells_not_equal.csv", index=False)

    # ---- tests and effects
    rng = np.random.default_rng(SEED)
    tests, effects = [], []
    for placement in runs.placement.unique():
        pr = runs[runs.placement == placement]
        for config in [c for c in pr.configuration.unique() if c != FULL]:
            for metric in METRICS:
                cells = []
                for scale in SCALES:
                    for u in UTILS:
                        vc = pr[(pr.configuration == config) & (pr.scale == scale) & (pr.U == u)][metric].to_numpy()
                        vf = pr[(pr.configuration == FULL) & (pr.scale == scale) & (pr.U == u)][metric].to_numpy()
                        if len(vc) == 0 or len(vf) == 0:
                            continue
                        cells.append((vc, vf))
                        effects.append(dict(configuration=config, placement=placement, period=scale, U=u, metric=metric, n_c=len(vc), n_FI=len(vf),
                                            hodges_lehmann=hodges_lehmann(vc, vf, metric), unit="factor (exp of median log-ratio)" if metric == "S" else "percentage points"))
                t_obs, p = perm_test(cells, rng)
                tests.append(dict(configuration=config, placement=placement, metric=metric, n_cells=len(cells), T_obs=t_obs, p_raw=p))
    tests = pd.DataFrame(tests)
    tests["p_holm"] = holm(tests.p_raw)
    tests["significant"] = tests.p_holm < ALPHA
    tests.to_csv(HERE / "tests.csv", index=False, float_format="%.6g")
    pd.DataFrame(effects).to_csv(HERE / "effects.csv", index=False, float_format="%.6g")
    print(f"{len(tests)} tests, seed {SEED}, {N_PERM} permutations; {int(tests.significant.sum())} significant after Holm")


if __name__ == "__main__":
    main()
