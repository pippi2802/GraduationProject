#!/usr/bin/env python3
"""Hierarchical bootstrap CIs (Kalibera & Jones 2013) of the effect of each configuration against full isolation, RQ1, warm-up excluded (N = 6).

    python3 bootstrap_ci.py

Reads the frozen data only; writes next to this script:
  bootstrap_ratios.csv      per configuration and cell: point ratios, 95% intervals, undefined-iteration counts, "above the largest A/A ratio" flags
  aa_splits.csv             per cell and split of the full-isolation rounds: point A/A ratios, 95% intervals, undefined counts
  aa_summary.csv            distribution of the A/A ratios per placement and metric, share of cells / splits whose interval excludes 1
  rounds_per_cell.csv       number of rounds (and retained jobs) per configuration and cell; cells with < 3 rounds are listed in report.txt
  report.txt                short text report

Ratios (configuration / full isolation, same cell):  tail spread = p99.9/median of R of the executed jobs;  loss ratio = loss rate / loss rate,
loss rate = (jobs with R > D + skipped releases) / (jobs + skipped), exactly the definitions of results_final.
Point ratios use all retained releases of the cell (the numbers of the frozen tables).
Bootstrap (ITER = 2000, seed fixed): resample the rounds of the cell with replacement; inside each resampled round resample its blocks of BLOCK = 100
consecutive releases with replacement (the release sequence of a round is: a job, then the releases skipped after it; a final incomplete block is not used);
pool the result and recompute the two statistics. Configuration and full isolation are resampled independently (the full-isolation replicates of a cell are drawn
once and paired by iteration with every configuration's replicates). Loss ratio is undefined in an iteration whose full-isolation loss rate is 0; those iterations
are left out of the interval and counted. 95% interval = 2.5th-97.5th percentile of the defined iterations.
A/A: the rounds of full isolation of a cell are split into two groups, all balanced splits (all splits into floor(n/2) and ceil(n/2) rounds, in both orders); the ratio
of group A to group B is computed with the same bootstrap.
"""
import itertools
import pathlib
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
OS_DATA = HERE.parent.parent / "os-experiments" / "analysis" / "data"
BASE_DATA = HERE.parent.parent / "kubedeadline-experiments" / "analysis" / "data"

FULL, SMT = "full isolation", "SMT enabled"
SCENARIOS = [("01", "isolcpus removed"), ("02", "nohz_full removed"), ("03", "rcu_nocbs removed"), ("04", "systemd containment removed"),
             ("05", "IRQ steering removed"), ("06", "boot-params bundle removed"), ("08", "frequency pinning removed")]
PLACEMENTS = [("single-core", "model1", "model1"), ("multi-core", "model5", "model5-phys")]
UTILS = [0.1, 0.5, 0.7, 0.94]
SCALES = ["tight", "soft"]
N_DROP, BLOCK, ITER, SEED = 6, 100, 2000, 20240601


def read_rounds(path):
    """{(scale, U): [ (R of the release sequence with nan for skipped releases, lost flag of every release) per round ]}"""
    df = pd.read_csv(path, usecols=["job_index", "R_wall_us", "deadline_miss", "skipped_before", "round", "scale", "U"])
    df = df[df.U.isin(UTILS) & (df.job_index >= N_DROP)].sort_values(["scale", "U", "round", "job_index"])
    out = {}
    for (scale, u, rnd), g in df.groupby(["scale", "U", "round"], sort=True):
        s = g.skipped_before.to_numpy(dtype=int)
        idx = np.repeat(np.arange(len(g)), 1 + s)
        first = np.r_[True, idx[1:] != idx[:-1]]
        r = np.where(first, g.R_wall_us.to_numpy()[idx], np.nan)
        lost = np.where(first, g.deadline_miss.to_numpy()[idx], 1).astype(np.int64)
        out.setdefault((scale, u), []).append((r, lost))
    return out


def prep(rounds):
    """per round: the R values of the whole sequence (point estimates) and the block arrays (bootstrap)"""
    res = []
    for r, lost in rounds:
        nb = len(r) // BLOCK
        res.append(dict(r=r, lost=lost, Rb=r[:nb * BLOCK].reshape(nb, BLOCK), Lb=lost[:nb * BLOCK].reshape(nb, BLOCK).sum(axis=1), nb=nb))
    return res


def stats(r, lost_sum, releases):
    x = r[~np.isnan(r)]
    med, p = np.percentile(x, [50, 99.9])
    return p / med, lost_sum / releases


def point(rs):
    r = np.concatenate([d["r"] for d in rs])
    return stats(r, sum(int(d["lost"].sum()) for d in rs), len(r))


def boot(rs, rng):
    """ITER replicates of (tail spread, loss rate) of the pooled cell"""
    tail, loss = np.empty(ITER), np.empty(ITER)
    n = len(rs)
    for i in range(ITER):
        parts, ls, rel = [], 0, 0
        for j in rng.integers(0, n, n):
            d = rs[j]
            sel = rng.integers(0, d["nb"], d["nb"])
            parts.append(d["Rb"][sel].ravel())
            ls += int(d["Lb"][sel].sum()); rel += d["nb"] * BLOCK
        tail[i], loss[i] = stats(np.concatenate(parts), ls, rel)
    return tail, loss


def ratio(a, b):
    """element-wise a / b, nan where b == 0"""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(b > 0, a / b, np.nan)


def interval(x):
    ok = x[~np.isnan(x)]
    return (np.percentile(ok, 2.5), np.percentile(ok, 97.5)) if len(ok) else (np.nan, np.nan)


def point_ratio(num, den):
    return num / den if den > 0 else np.nan


def one_cell(args):
    placement, scale, u, full_rounds, configs, seed = args
    rng = np.random.default_rng(seed)
    fr = prep(full_rounds)
    ft, fl = boot(fr, rng)
    fp = point(fr)
    ratios, aa = [], []
    for name, cfg_rounds in configs.items():
        cr = prep(cfg_rounds)
        ct, cl = boot(cr, rng)
        cp = point(cr)
        lr = ratio(cl, fl)
        t_lo, t_hi = interval(ct / ft)
        l_lo, l_hi = interval(lr)
        ratios.append(dict(placement=placement, configuration=name, scale=scale, U=u, rounds=len(cr), full_rounds=len(fr),
                           tail_ratio=cp[0] / fp[0], tail_lo=t_lo, tail_hi=t_hi,
                           loss_rate_pct=100 * cp[1], full_loss_rate_pct=100 * fp[1], loss_ratio=point_ratio(cp[1], fp[1]), loss_lo=l_lo, loss_hi=l_hi,
                           loss_undefined_iters=int(np.isnan(lr).sum())))
    n = len(fr)
    sizes = sorted({n // 2, n - n // 2})
    cache = {}
    def sub(ids):
        if ids not in cache:
            part = [fr[i] for i in ids]
            cache[ids] = (point(part),) + boot(part, rng)
        return cache[ids]
    if n >= 2:
        for k in sizes:
            for a in itertools.combinations(range(n), k):
                b = tuple(i for i in range(n) if i not in a)
                (pa, ta, la), (pb, tb, lb) = sub(a), sub(b)
                lr = ratio(la, lb)
                t_lo, t_hi = interval(ta / tb)
                l_lo, l_hi = interval(lr)
                aa.append(dict(placement=placement, scale=scale, U=u, group_a="+".join(map(str, a)), group_b="+".join(map(str, b)),
                               tail_ratio=pa[0] / pb[0], tail_lo=t_lo, tail_hi=t_hi, loss_ratio=point_ratio(pa[1], pb[1]), loss_lo=l_lo, loss_hi=l_hi,
                               loss_undefined_iters=int(np.isnan(lr).sum())))
    return ratios, aa


def main():
    jobs, rounds_rows = [], []
    for pi, (placement, model, base_file) in enumerate(PLACEMENTS):
        full = read_rounds(BASE_DATA / f"{base_file}.csv")
        sources = [(name, read_rounds(OS_DATA / f"{code}-{model}.csv")) for code, name in SCENARIOS]
        if placement == "multi-core":
            sources.append((SMT, read_rounds(BASE_DATA / "model5-smt.csv")))
        for scale in SCALES:
            for u in UTILS:
                key = (scale, u)
                rounds_rows.append(dict(placement=placement, configuration=FULL, scale=scale, U=u, rounds=len(full[key]), jobs=sum(int((~np.isnan(r)).sum()) for r, _ in full[key])))
                configs = {}
                for name, data in sources:
                    if key in data:
                        configs[name] = data[key]
                        rounds_rows.append(dict(placement=placement, configuration=name, scale=scale, U=u, rounds=len(data[key]), jobs=sum(int((~np.isnan(r)).sum()) for r, _ in data[key])))
                    else:
                        rounds_rows.append(dict(placement=placement, configuration=name, scale=scale, U=u, rounds=0, jobs=0))
                jobs.append((placement, scale, u, full[key], configs, SEED + 1000 * pi + 10 * SCALES.index(scale) + UTILS.index(u)))
    with Pool() as pool:
        results = pool.map(one_cell, jobs)
    ratios = pd.DataFrame([r for rr, _ in results for r in rr])
    aa = pd.DataFrame([r for _, a in results for r in a])
    rounds = pd.DataFrame(rounds_rows)
    rounds.to_csv(HERE / "rounds_per_cell.csv", index=False)
    aa.to_csv(HERE / "aa_splits.csv", index=False)

    # A/A summary and flags
    summ = []
    for placement in aa.placement.unique():
        a = aa[aa.placement == placement]
        for metric, col in [("tail spread", "tail"), ("loss", "loss")]:
            pr = a[f"{col}_ratio"]
            d = a[~a[f"{col}_lo"].isna()]
            cells = d.groupby(["scale", "U"]).apply(lambda g: bool(((g[f"{col}_lo"] > 1) | (g[f"{col}_hi"] < 1)).any()), include_groups=False)
            summ.append(dict(placement=placement, metric=metric, splits=len(a), splits_defined=int(pr.notna().sum()), aa_min=pr.min(), aa_p5=pr.quantile(.05), aa_median=pr.median(),
                             aa_p95=pr.quantile(.95), aa_max=pr.max(), splits_interval_excludes_1=int(((d[f"{col}_lo"] > 1) | (d[f"{col}_hi"] < 1)).sum()),
                             splits_with_interval=len(d), share_splits_excluding_1=((d[f"{col}_lo"] > 1) | (d[f"{col}_hi"] < 1)).mean() if len(d) else np.nan,
                             cells=len(cells), cells_any_split_excluding_1=int(cells.sum()), share_cells_excluding_1=cells.mean() if len(cells) else np.nan,
                             undefined_iters_total=int(a.loc[:, "loss_undefined_iters"].sum()) if metric == "loss" else 0))
    summ = pd.DataFrame(summ)
    summ.to_csv(HERE / "aa_summary.csv", index=False)
    mx = {(r.placement, r.metric): r.aa_max for r in summ.itertuples()}
    ratios["above_aa_max_tail"] = [lo > mx[(p, "tail spread")] for p, lo in zip(ratios.placement, ratios.tail_lo)]
    ratios["above_aa_max_loss"] = [bool(lo > mx[(p, "loss")]) if not np.isnan(lo) else False for p, lo in zip(ratios.placement, ratios.loss_lo)]
    ratios["interval_excludes_1_tail"] = (ratios.tail_lo > 1) | (ratios.tail_hi < 1)
    ratios["interval_excludes_1_loss"] = (ratios.loss_lo > 1) | (ratios.loss_hi < 1)
    ratios["iterations"] = ITER
    ratios.to_csv(HERE / "bootstrap_ratios.csv", index=False)

    low = rounds[(rounds.rounds < 3) & (rounds.rounds > 0)]
    with open(HERE / "report.txt", "w") as f:
        f.write(f"bootstrap: {ITER} iterations, block {BLOCK} releases, N_DROP {N_DROP}, seed {SEED}\n\n")
        f.write("rounds per cell (min / max over cells with data), by configuration group\n")
        f.write(rounds[rounds.rounds > 0].groupby(["placement", "configuration"]).rounds.agg(["min", "max"]).to_string() + "\n\n")
        f.write("cells with fewer than 3 rounds (excluding not run): " + ("none\n" if low.empty else "\n" + low.to_string() + "\n"))
        f.write("cells not run (0 rounds): " + str(int((rounds.rounds == 0).sum())) + "\n")
        f.write("cells whose full-isolation reference has fewer than 4 rounds: \n" + rounds[(rounds.configuration == FULL) & (rounds.rounds < 4)].to_string() + "\n\n")
        f.write("A/A summary\n" + summ.to_string() + "\n\n")
        f.write("loss-ratio iterations undefined (full-isolation loss rate 0): total %d of %d (%d cell-configurations, %d with all %d undefined)\n" % (
            ratios.loss_undefined_iters.sum(), ITER * len(ratios), len(ratios), int((ratios.loss_undefined_iters == ITER).sum()), ITER))
        f.write("configuration cells above the largest A/A ratio: tail %d of %d, loss %d of %d\n" % (
            ratios.above_aa_max_tail.sum(), len(ratios), ratios.above_aa_max_loss.sum(), int(ratios.loss_lo.notna().sum())))
    print((HERE / "report.txt").read_text())


if __name__ == "__main__":
    main()
