# RQ1 ablation figures

Rerun: `../../../.venv/bin/python make_rq1_figures.py` (needs numpy, pandas, matplotlib). Same data, N = 6 warm-up exclusion and
definitions as `../make_results_final.py` (not modified, not imported). SMT is not part of the ablation.

Each figure compares every reverted lever with full isolation (FI), one row per lever, one dot per utilization U (light = low, dark = high),
joined by a grey line from the smallest to the largest value.
- Left panel: tail spread S = p99.9(R) / median(R) of every configuration, full isolation included (top row, no p-value); log axis, dashed line at 1 (p99.9 = median).
- Right panel (full isolation row empty, it is the reference): miss-rate increase dM = M_c - M_FI in percentage points, M = (misses + skipped) / (completed + skipped); dashed line at 0.
- The largest value of a row is written next to its dot (left if >= 1.5, right if >= 0.25 pp).
- Values below 1 (left) or 0 (right) are better than FI. Cells not run (isolcpus reverted, U = 0.94) are absent.
- Holm p (right of the left panel, tail spread only; none for miss rate): one-sided permutation test of S against FI, from `../../../rq1_significance/tests.csv`; one value per lever and placement, pooled over both periods and all U, so identical in the tight and soft figure; bold * = p_Holm < 0.05. These are p-values, not confidence levels.
- Axis limits (left 0.9-70, right -0.5 to 6 pp) and row order are identical in all figures.

Files: `rq1_singlecore_tight`, `rq1_singlecore_soft` (P = 100 ms), `rq1_multicore_tight`, `rq1_multicore_soft` (.svg/.png),
`rq1_figures_values.csv` (S, M, rho, dM per cell), `run.log` (output of the three checks).
