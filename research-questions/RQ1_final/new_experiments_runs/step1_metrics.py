#!/usr/bin/env python3
"""STEP 1 - per-run metrics, one row per run -> output/step1_runs.csv

Lost release = job with deadline_miss = 1 (R > P), or a skipped release. Skipped releases are not rows: they are detected from gaps in
release_us (gap ~ 2P = 1 skipped, ~ 3P = 2, ...). skipped_col (column skipped_before) is written only as a cross-check.
  miss_skip_pct     100 * (misses + skipped) / (jobs + skipped)
  m_k100            100 - (largest number of lost releases in any window of 100 consecutive releases), windows over the release sequence
  longest_lost_run  longest run of consecutive lost releases
  tail_spread       p99.9(R) / median(R) of the executed jobs
  p99_over_P        p99(R) / P
"""
import numpy as np
import pandas as pd

import common as cm


def run_metrics(a, P):
    seq, skipped = cm.lost_sequence(a, P)
    n = len(a["job_index"])
    misses = int(a["deadline_miss"].sum())
    R = a["R_wall_us"]
    ww = cm.worst_window_lost(seq)
    return dict(n_jobs=n, misses=misses, skipped_gap=skipped, skipped_col=int(a["skipped_before"].sum()),
                miss_skip_pct=100.0 * (misses + skipped) / (n + skipped),
                worst_window_lost=ww, m_k100=cm.K_WINDOW - ww, longest_lost_run=cm.longest_run(seq),
                tail_spread=float(np.percentile(R, 99.9) / np.median(R)), p99_over_P=float(np.percentile(R, 99) / P))


def compute():
    runs, _ = cm.get_runs()
    rows = []
    for (pl, c, s, u, r), a in runs.items():
        rows.append(dict(placement=pl, configuration=c, scale=s, U=u, round=r, **run_metrics(a, cm.PERIOD[s])))
    t = pd.DataFrame(rows)
    order = {c: i for i, c in enumerate(cm.CONFIGS)}
    t = t.sort_values(["placement", "scale", "U", "configuration", "round"], key=lambda col: col.map(order) if col.name == "configuration" else col).reset_index(drop=True)
    return t


def main():
    cm.OUT.mkdir(parents=True, exist_ok=True)
    t = compute()
    t.to_csv(cm.OUT / "step1_runs.csv", index=False)
    d = (t.skipped_gap != t.skipped_col)
    print(f"step 1: {len(t)} runs; skipped releases from gaps vs column skipped_before differ in {int(d.sum())} runs "
          f"(total {int(t.skipped_gap.sum())} vs {int(t.skipped_col.sum())})")
    return 0


if __name__ == "__main__":
    main()
