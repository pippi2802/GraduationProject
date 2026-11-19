# Pooled earlier campaign + rerun (tmp, not committed)
Run: `../../.venv/bin/python pooled.py`. Earlier campaign (os-experiments/analysis/data + kubedeadline-experiments full isolation, 4 rounds x 5000 jobs) and rerun
(os-experiments/test-results/results, 4 rounds x 5000 jobs) pooled per cell: 8 runs, or 4 merged rounds (earlier round i + rerun round i, ~10000 jobs).
K_reps / matrix_M are not loaded (differ between batches). No job dropped; SMT not included (not in rerun); n/r = not run.
M = 100 (misses+skipped)/(jobs+skipped); dM = M_config - M_full isolation [pp]; S = p99.9(R)/median(R) of pooled R.
Files: table_spread_*.tex, table_increase_*.tex (dM instead of the rate), table_rounds_*.tex (x/4 merged rounds above full-isolation max),
rq1_{singlecore,multicore}_{tight,soft}.{svg,png}, pooled_cells.csv (S, M, dM also per batch A/B), pooled_merged_rounds.csv.
