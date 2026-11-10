# rq1_significance

Does a configuration differ from full isolation (FI) by more than run-to-run variability explains? Read-only on the frozen data; nothing outside this folder was changed.

Run: `python3 significance_tests.py` then `python3 compare_frozen.py` (needs numpy, pandas).

## Procedure

- **Data, configurations, cells, warm-up:** as `os-experiments/results_final/make_results_final.py`: the same CSVs, the same 7 levers (+ SMT enabled for multi-core; scenario 07 is not in the frozen tables, so not here), cells = period (tight, soft) x U in {0.1, 0.5, 0.7, 0.94}, the first N = 6 jobs of every round dropped with the releases skipped after them.
- **Run:** one round of one cell. For each run (`runs.csv`): S = p99.9(R_wall_us) / median(R_wall_us) of the executed jobs, M = 100 x (misses + skipped) / (jobs + skipped), same formulas as the frozen tables but on one round.
- **Test**, per configuration c != FI, placement and metric (S, M), cells with at least one run of both c and FI:
  1. in each cell the runs of c and FI are ranked together, mid-ranks for ties;
  2. T_obs = sum over cells of the rank sums of c;
  3. 100,000 permutations; the c/FI labels are shuffled within every cell independently, never across cells; T recomputed;
  4. one-sided p = (1 + #{T_perm >= T_obs}) / (1 + 100000), "worse" = larger S or larger M. The smallest possible p is therefore 1e-5;
  5. Holm over all 30 tests (14 single-core, 16 multi-core), `significant` = p_holm < 0.05.
- **Seed:** 20261104 (numpy `default_rng`), one generator used in a fixed test order, so the output is reproducible.
- **Effect size** (`effects.csv`), per cell: Hodges-Lehmann estimate = median of all pairwise differences (c run minus FI run). For S it is exp(median of log S_c - log S_FI), a factor; for M it is the difference in percentage points.

## Runs per cell

Every cell of every configuration has 4 runs (rounds 1-4), all listed in `run_counts.csv`. Cells that do not have the same number of runs for c and FI, or that were not run (`cells_not_equal.csv`):

- **Unequal:** multi-core, soft, U = 0.1: FI has 3 runs (rounds 2, 3, 4; round 1 is missing in the frozen data), every configuration has 4 (rounds 1-4). Affects 8 configurations (IRQ steering, SMT, boot-params, frequency pinning, isolcpus, nohz_full, rcu_nocbs, systemd). The test uses the 4 vs 3 runs available.
- **Not run:** isolcpus removed at U = 0.94, tight and soft, both placements (4 cells). Those configurations are tested on 6 cells instead of 8.

## Points to keep in mind

- With 4 runs against 4 runs, a cell has only 70 distinct labelings. The test combines up to 8 cells (70^8 labelings), which is what makes small p-values possible, but a single cell carries little power by itself.
- The statistic T is a plain sum of rank sums, as specified. With equal run counts in all cells this is the van Elteren statistic (equal weights); with the unequal cell above, that cell is weighted slightly differently from the van Elteren weights.
- Multi-core FI (`model5-phys.csv`) has a `thread` column: two target threads per round (9,988 jobs per round against 4,994 for the lever runs). The frozen tables pool both threads, and so do these runs, so a multi-core FI run is a pool of two threads and a configuration run is one thread. Any effect of that difference is part of the comparison.
- Runs of different configurations come from different campaigns (different times), so the test cannot separate a configuration effect from platform drift between campaigns. Only FI run-to-run variability enters the null distribution.

## Result

`tests.csv` has the 30 tests, 6 are significant after Holm:

| placement | configuration | metric | p_holm |
|---|---|---|---|
| single-core | isolcpus removed | S, M | 0.0003, 0.0008 |
| single-core | nohz_full removed | S | 0.016 |
| multi-core | SMT enabled | M | 0.0003 |
| multi-core | rcu_nocbs removed | S, M | 0.0003, 0.0008 |

Close but not significant: multi-core frequency pinning removed (M, p_holm = 0.056), single-core systemd containment removed (S, p_holm = 0.099), multi-core isolcpus removed (M, p_holm = 0.12). SMT enabled is not significant on S, as expected: it shifts the median, so the tail-to-median ratio does not move (the frozen figure says the same).

## Comparison with the frozen results

The frozen outputs have no explicit "has an effect" label. `compare_frozen.py` uses this rule: a setting has an effect at a placement when its relative spread in the frozen table is at least 2 in some cell. The frozen values split into two groups, at least 9.4 or at most 1.61, so the choice of threshold between 1.7 and 9 does not matter. Full table: `comparison_frozen.csv`.

- Frozen effect and significant (agree): single-core isolcpus, nohz_full; multi-core SMT, rcu_nocbs.
- No frozen effect and not significant (agree): the other 11 settings.
- **Disagreement: single-core systemd containment removed.** Frozen: relative spread up to 11.5 (soft, U = 0.1). Test: not significant (p_holm = 0.099 on S, 0.52 on M). The four runs of that cell have S = 1.02, 1.19, 11.9, 12.5: the spread comes from 2 of the 4 rounds, so the pooled cell value shows an effect while the round-to-round comparison against FI does not reach significance after correcting for 30 tests.
