#!/usr/bin/env python3
"""Tail check, full isolation (read-only on the frozen data). Warm-up: first N_DROP = 6 jobs of every round dropped.
Cells: single-core (model1), multi-core (model5-phys), U = 0.1 tight+soft; multi-core tight U = 0.5 as contrast.
R = dispatch_latency + C + mid_job_preempt (exactly, up to rounding): R = finish - release, dispatch = start - release, C + mid = finish - start.
Tail jobs: R > p99.9(R) of the cell. 'Largest component of R - median(R)': each component's excess over its own cell median,
d - med(d), C - med(C), m - med(m); the component with the largest excess wins (excesses sum to R - sum of medians, not exactly R - med(R)).
"""
import pathlib, numpy as np, pandas as pd
HERE = pathlib.Path(__file__).resolve().parent
D = HERE.parent / "kubedeadline-experiments" / "analysis" / "data"
N_DROP = 6
COMP = [("dispatch_latency_us", "dispatch"), ("mid_job_preempt_us", "mid_preempt"), ("C_cputime_us", "C")]
CELLS = [("single-core", "model1", "tight", 0.1), ("single-core", "model1", "soft", 0.1),
         ("multi-core", "model5-phys", "tight", 0.1), ("multi-core", "model5-phys", "soft", 0.1),
         ("multi-core", "model5-phys", "tight", 0.5)]
rows, shares = [], []
for place, f, scale, u in CELLS:
    df = pd.read_csv(D / f"{f}.csv")
    g = df[(df.scale == scale) & (df.U == u) & (df.job_index >= N_DROP)]
    r = g.R_wall_us
    p999 = np.percentile(r, 99.9)
    tail = g[r > p999]
    row = dict(placement=place, scale=scale, U=u, jobs=len(g), tail_jobs=len(tail), R_median=r.median(), R_p999=p999)
    ex = pd.DataFrame({k: tail[c] - g[c].median() for c, k in COMP})
    win = ex.idxmax(axis=1).value_counts(normalize=True)
    for c, k in COMP:
        row |= {f"{k}_median": g[c].median(), f"{k}_p999": np.percentile(g[c], 99.9),
                f"{k}_tail_median": tail[c].median(), f"{k}_tail_max": tail[c].max(), f"{k}_largest_share": float(win.get(k, 0.0))}
    rows.append(row)
out = pd.DataFrame(rows)
out.to_csv(HERE / "tail_check.csv", index=False, float_format="%.3f")
with open(HERE / "tail_check.txt", "w") as fh:
    for _, r in out.iterrows():
        fh.write(f"\n== {r.placement}, {r.scale}, U={r.U}: {int(r.jobs)} jobs, {int(r.tail_jobs)} tail jobs (R > p99.9), R median {r.R_median:.1f} p99.9 {r.R_p999:.1f} us\n")
        fh.write(f"{'component':12s}{'median':>11s}{'p99.9':>11s}{'tail median':>13s}{'tail max':>11s}{'largest share':>15s}\n")
        for _, k in COMP:
            fh.write(f"{k:12s}{r[k+'_median']:11.1f}{r[k+'_p999']:11.1f}{r[k+'_tail_median']:13.1f}{r[k+'_tail_max']:11.1f}{r[k+'_largest_share']:15.2f}\n")
print(open(HERE / "tail_check.txt").read())
