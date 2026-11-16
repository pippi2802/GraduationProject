#!/usr/bin/env python3
"""STEP 0 - validity of the rerun data. Writes output/step0_validity_runs.csv and output/step0_report.md.
Exit status 1 (and the report lists the failing runs) if any check fails; run_all.py then stops.

a) every run has EXPECTED_JOBS (5000) jobs and every cell has 4 rounds;
b) median C of a run / median C of full isolation (same placement, P, U, round): 0.97-1.03 for every configuration except
   frequency pinning removed, for which < 1 is expected;
c) full isolation: median C / (0.7 * Q) in 0.97-1.03 for every run (Q = U * P).
"""
import sys

import numpy as np
import pandas as pd

import common as cm

LO, HI = 0.97, 1.03


def main():
    cm.OUT.mkdir(parents=True, exist_ok=True)
    runs, missing = cm.get_runs()
    rows = []
    for (pl, c, s, u, r), a in runs.items():
        P = cm.PERIOD[s]
        Q = u * P
        rows.append(dict(placement=pl, configuration=c, scale=s, U=u, round=r, n_jobs=len(a["job_index"]),
                         median_C_us=float(np.median(a["C_cputime_us"])), Q_us=Q))
    t = pd.DataFrame(rows)
    fi = t[t.configuration == cm.FULL].set_index(["placement", "scale", "U", "round"]).median_C_us
    key = list(zip(t.placement, t.scale, t.U, t["round"]))
    t["fi_median_C_us"] = [fi.get(k, np.nan) for k in key]
    t["ratio_to_fi"] = t.median_C_us / t.fi_median_C_us
    t["fi_over_0.7Q"] = np.where(t.configuration == cm.FULL, t.median_C_us / (cm.HEADROOM * t.Q_us), np.nan)

    fails = []                       # (check, run description, detail)
    for k in missing:
        fails.append(("a", k, "run missing (no jobs.csv)"))
    for _, r in t.iterrows():
        k = (r.placement, r.configuration, r.scale, r.U, int(r["round"]))
        if r.n_jobs != cm.EXPECTED_JOBS:
            fails.append(("a", k, f"{int(r.n_jobs)} jobs, expected {cm.EXPECTED_JOBS}"))
    for (pl, c, s, u) in cm.cells():
        have = sorted(r for r in cm.ROUNDS if (pl, c, s, u, r) in runs)
        if have != cm.ROUNDS:
            fails.append(("a", (pl, c, s, u), f"cell has rounds {have}, expected {cm.ROUNDS}"))
    for _, r in t[t.configuration != cm.FULL].iterrows():
        k = (r.placement, r.configuration, r.scale, r.U, int(r["round"]))
        x = r.ratio_to_fi
        if np.isnan(x):
            fails.append(("b", k, "no full-isolation run to compare with"))
        elif r.configuration == cm.FREQ:
            if not x < 1:
                fails.append(("b", k, f"ratio {x:.4f}, expected < 1"))
        elif not (LO <= x <= HI):
            fails.append(("b", k, f"ratio {x:.4f}, expected {LO}-{HI}"))
    for _, r in t[t.configuration == cm.FULL].iterrows():
        k = (r.placement, r.configuration, r.scale, r.U, int(r["round"]))
        x = r["fi_over_0.7Q"]
        if not (LO <= x <= HI):
            fails.append(("c", k, f"median C / (0.7 Q) = {x:.4f}, expected {LO}-{HI}"))

    t.sort_values(["placement", "scale", "U", "configuration", "round"]).to_csv(cm.OUT / "step0_validity_runs.csv", index=False)

    ok = not fails
    L = [f"# Step 0 - validity: {'PASSED' if ok else 'FAILED'}", "",
         f"Runs loaded: {len(runs)} of {len(runs) + len(missing)} planned ({len(cm.cells())} cells x {len(cm.ROUNDS)} rounds). Data: `{cm.DATA}`.", "",
         "| check | rule | failing runs |", "|---|---|---|",
         f"| a | {cm.EXPECTED_JOBS} jobs per run, 4 rounds per cell | {sum(f[0] == 'a' for f in fails)} |",
         f"| b | median C / median C of full isolation (same placement, P, U, round): {LO}-{HI}; frequency pinning removed: < 1 | {sum(f[0] == 'b' for f in fails)} |",
         f"| c | full isolation: median C / (0.7 Q): {LO}-{HI} | {sum(f[0] == 'c' for f in fails)} |", ""]
    if ok:
        L.append("All checks passed.")
    else:
        L.append("**A check failed. The analysis stops here (steps 1-5 and figures were not run).** Failing runs:")
        L.append("")
        for chk in "abc":
            sub = [f for f in fails if f[0] == chk]
            if not sub:
                continue
            L += [f"## Check {chk} ({len(sub)})", "", "| run (placement, configuration, scale, U[, round]) | detail |", "|---|---|"]
            for _, k, d in sub:
                L.append(f"| {', '.join(str(x) for x in k)} | {d} |")
            L.append("")
    if len(t):
        L += ["## Summary of the ratios (all runs loaded)", "",
              f"- median C / full isolation, all configurations except frequency pinning removed: min {t[(t.configuration != cm.FULL) & (t.configuration != cm.FREQ)].ratio_to_fi.min():.4f}, "
              f"max {t[(t.configuration != cm.FULL) & (t.configuration != cm.FREQ)].ratio_to_fi.max():.4f}",
              f"- median C / full isolation, frequency pinning removed: min {t[t.configuration == cm.FREQ].ratio_to_fi.min():.4f}, max {t[t.configuration == cm.FREQ].ratio_to_fi.max():.4f}",
              f"- full isolation median C / (0.7 Q): min {t['fi_over_0.7Q'].min():.4f}, max {t['fi_over_0.7Q'].max():.4f}", ""]
    (cm.OUT / "step0_report.md").write_text("\n".join(L) + "\n")
    print(f"step 0: {'PASSED' if ok else 'FAILED'} ({len(fails)} failing items: " + ", ".join(f"{c}={sum(f[0] == c for f in fails)}" for c in 'abc') + ")")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
