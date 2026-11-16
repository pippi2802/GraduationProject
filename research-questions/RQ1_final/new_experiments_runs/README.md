# RQ1 rerun analysis (4 rounds)

Uses only the rerun data: `../os-experiments/test-results/results/<config>_round<N>/<scale>/U<u>/jobs.csv` (544 runs: 136 cells x 4 rounds).
Run: `../.venv/bin/python run_all.py` (stops after step 0 if a validity check fails) or `... run_all.py --ignore-step0`.
Outputs in `output/` (CSV for every step, LaTeX tables for steps 2-5, figures). Nothing here interprets the results.

## Status of step 0
Step 0 FAILED (check a passed; checks b and c failed, see `output/step0_report.md` for every failing run). The analysis was continued on request
(`--ignore-step0`); the failing runs are part of the data used below.

## Definitions (fixed before the results were seen)
- Configurations and order as in the existing figures: full isolation, isolcpus, nohz_full, rcu_nocbs, systemd containment, IRQ steering, frequency pinning,
  boot-params bundle, then `all defaults` (scenario 07, new in the rerun). SMT is not part of the rerun. n/r = not run (U = 0.94 without isolcpus and in all defaults).
- Placements: single-core = `<NN>-model1` and `model1` (full isolation); multi-core = `<NN>-model5` and `model5-phys`.
- Run = configuration x placement x P x U x round, 5000 recorded jobs. Q = U P. P = 10 ms (tight) or 100 ms (soft).
- Lost release = job with deadline_miss = 1, or skipped release. Skipped releases are not rows; they come from gaps in release_us (round(gap / P) - 1 per gap).
  The column skipped_before is used only as a cross-check (identical in all 544 runs: 2230 skipped releases). The last job of a run has no following release.
- Step 1: miss+skip % = 100 (misses + skipped) / (jobs + skipped); m = 100 - max lost releases in any window of 100 consecutive releases; longest run of
  consecutive lost releases; tail spread = p99.9(R) / median(R) (numpy linear percentiles); p99(R) / P.
- Step 2: x/4 = rounds whose miss+skip % is strictly larger than the maximum of the four full-isolation rounds of the same cell; full isolation min-max per cell.
- Step 3: one-sided stratified Wilcoxon rank-sum permutation test, strata = cells with runs of both, mid-ranks, 100000 permutations, p = (1 + #) / (1 + 100000),
  seed 20261104, Holm within placement and metric. Hodges-Lehmann shift = median of the pooled within-stratum pairwise differences (configuration minus full
  isolation); percentage points for miss+skip, factor exp(median log ratio) for tail spread.
- Step 4: per run, then median [min-max] over the four rounds. Ratios to full isolation use the same round. Dispatch p99 and interruptions per second exclude jobs with C > Q;
  an interruption is a job with mid_job_preempt_us > 10 us; execution time = finish - start. Involuntary context switches per second use all jobs.
  CV = sample std / mean of C. Share of misses with C > Q uses missed jobs (rows).
- Step 5: missed jobs with C <= Q whose mid_job_preempt_us is within 10% of P - Q; four rounds pooled per cell.
- Figures: cell value = four rounds pooled (tail spread: pooled R; miss+skip: lost / releases); heatmaps: worst (smallest m, longest run) over the four rounds.
  Miss+skip on a log axis; a rate of 0 is an open marker on the axis labelled 0. Holm p in the figures are the step-3 tests (pooled over the cells).

## Files
step0_validity.py, step1_metrics.py ... step5_throttle.py, make_figures.py, common.py, run_all.py.
Table style: the existing RQ1 result tables (`os-experiments/results_final/table_*.tex`); `tab:rq1-acts-single-core` is not in the repository.

## Platform (round) effects: `platform_*.py`, outputs in `output/platform/`
Separates configuration effects from round effects; computed, not interpreted. Run order: `platform_step0_times.py` (needs `input/run_times.csv`, see its docstring;
the wall-clock times exist only on cp-0), `platform_effects.py` (per-run metrics, Friedman tests, sum-of-squares shares, within-round differences, tables),
`platform_figures.py` (4 figures, placement x period, pdf+png). Definitions are in the docstring of `platform_effects.py` (fixed before the results were seen):
five metrics per run, 9 configurations x 4 rounds per placement x P x U (7 configurations at U = 0.94), Friedman tests with Monte Carlo permutation p-values
(100000 permutations, seed 20261104; asymptotic p alongside), Holm within placement and metric, additive model on log(value + c) without interaction.
