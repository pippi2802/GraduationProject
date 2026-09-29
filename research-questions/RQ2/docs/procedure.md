# Procedure: deriving CBS reservation parameters from measurement

Five steps. Tolerance levels (per-job miss probability `p`, burst limit,
confidence level) live in `configs/requirements.yaml`, never hard-coded.
Status column: which batch implements the script.

## Step 1 - Profiling under stress

**Purpose.** Measure per-job CPU time `C_k` for the task under a range of
interference conditions, so Steps 2-3 can characterize its tail and the
effect of contention.

**Inputs.** `configs/campaign_profiling.yaml`, `configs/platform.yaml`.

**Procedure.** For each deployment (single-core, multi-core) and
condition (baseline; cache/memory enemy at each dial level; loaded
housekeeping), run `sessions_per_condition` repetitions of the workload
with a generous budget (`Q = factor * T`, `--overrun skip`) so the
reservation itself never binds - Step 1 measures the *application's*
timing, not the reservation's effect. Enemies (`stress/enemy.c`) are
pinned to non-RT cores (or, at the highest dial level, sharing the
housekeeping core), never to the cores under measurement.

**Outputs.** `results/raw/<profiling session>/<deployment>/<condition>/<run_id>/` -
CSV + metadata per instance, per `docs/data_layout.md`.

**Implemented by.** `rq2/orchestration/campaign.py`
(`configs/campaign_profiling.yaml`), `rq2/workload/rt_video.py`,
`stress/enemy.c`, `stress/hk_load.sh`. **Status: Batch 1, done.**

## Step 2 - Tail estimation

**Purpose.** From each condition's measured `C_k`, estimate an upper
confidence bound on the `(1-p)`-quantile of the execution-time
distribution, for each `p` in `configs/requirements.yaml`.

**Inputs.** Per-instance `cpu_ns` traces from Step 1. Jobs with
`cpu_ns > stall_factor * T` (default `stall_factor = 2.0`) are treated as
VM stalls: excluded from fitting, reported separately.

**Method A (primary).** Empirical `(1-p)`-quantile. i.i.d. upper
confidence bound via the order statistic `x_(k)`, the smallest `k` with
`P(Binomial(N, 1-p) <= k-1) >= 1-alpha`. Dependence-aware upper bound via
moving-block bootstrap (block length 500, 1000 resamples, `(1-alpha)`
percentile). Flagged if `N*p < 10` (too few expected exceedances for the
order-statistic bound to be reliable).

**Extremal index `theta`** (dependence in the tail), via the intervals
estimator (Ferro & Segers) on exceedances of the empirical 0.99 quantile.
With inter-exceedance gaps `T_i` (`n` exceedances):

```
max T_i <= 2:  theta = 2 (sum T_i)^2 / ((n-1) sum T_i^2)
otherwise:     theta = 2 (sum (T_i-1))^2 / ((n-1) sum (T_i-1)(T_i-2)), capped at 1
```

**Method B (cross-check).** Block maxima, block length `b` in
`{250, 500, 1000}` (a length is skipped if it yields < 50 blocks).
Independence diagnostics on the block maxima: Ljung-Box (lags 1-10) and a
runs test; KPSS on a thinned series. Fit GEV (`scipy.stats.genextreme`;
scipy's `c = -xi`, report `xi`) and Gumbel. Convert the per-job `p` to a
block-level `p_b = 1 - (1-p)^(b*theta)`, bound `= ppf(1 - p_b)`.
Parametric bootstrap upper bound.

**Decision.** If `N*p >= 10`, use Method A's bootstrap UCB; otherwise use
Method B's GEV bootstrap UCB. Flag if A and B differ by more than 15%.

**Outputs.** JSON + CSV per condition/instance/`p`: median, Method A/B
bounds, `theta`, GEV parameters, flags. Plots: exceedance curve
(`1 - ECDF`, log y) with fitted tails, QQ plot.

**Implemented by.** `rq2/procedure/tail_estimation.py`. **Status: Batch 2.**

### Step 2b - Tail validation

**Held-out test.** Given a bound fit on trace A, count exceedances in a
held-out trace B; cluster exceedances fewer than `r = 5` jobs apart into
one cluster; compare the observed cluster count against the expected
`M * p * theta` via a one-sided binomial test.

**Convergence.** Recompute the bound on the first 25/50/75/100% of a
trace, to see how quickly it stabilizes.

**Implemented by.** `rq2/procedure/tail_validation.py`. **Status: Batch 2.**

## Step 3 - Inflation factors

**Purpose.** Turn the baseline tail bound into a bound that accounts for
core-count contention, housekeeping-core interference, and
session-to-session drift.

- `alpha_cores(m) = C_p(stress, m) / C_p(baseline)`, using the larger of
  the cache- and memory-enemy bound, per dial level `m`.
- `alpha_OS = C_p(loaded housekeeping) / C_p(baseline)`.
- `alpha_drift`: from baseline runs across several deployments/sessions,
  both the max ratio to a reference instance and
  `c_RSD = 100 * std / mean` of the baseline medians and bounds. Applied
  (`alpha_drift` computed) only if `c_RSD` exceeds a configurable
  threshold (default 5%); otherwise `alpha_drift = 1`. The decision is
  reported either way.

Each factor is reported with its spread across sessions/instances.

**Implemented by.** `rq2/procedure/inflation.py`. **Status: Batch 2.**

## Step 4 - Budget via an analytical CBS model

**Model.** One task per reservation, hard CBS, budget `Q` per period `T`,
`D = T`. Jobs released every `T`; unfinished work carries over
(`--overrun continue`). Backlog recursion (Lindley form):

```
v_{k+1} = max(0, v_k + C_k - Q)
```

Job `k` meets its deadline iff `v_k + C_k <= Q`. Execution times `C_k`
i.i.d. with the input samples' empirical distribution (optionally scaled
by a factor), discretized with step `delta` (default 0.1 ms). The
stationary distribution of `v` is obtained by iterating the discretized
recursion, truncated at a configurable max backlog (truncation mass
reported); the model reports "unstable" if `mean(C) >= Q`. Output:
`P(deadline met)` / miss probability for a given `Q`; a risk curve over a
`Q` grid, reporting the smallest `Q` with miss probability `<= p` for
each `p` in `configs/requirements.yaml`.

A companion function replays the same recursion on the measured
*sequence* (not i.i.d. resampled), so the effect of temporal dependence
(quantified by `theta` in Step 2) can be compared against the i.i.d.
prediction.

**Self-test.** Agreement with a Monte Carlo simulation of the same
recursion under i.i.d. sampling (within statistical error), and a
trivial case (`C < Q` always -> zero misses).

> This model follows the probabilistic CBS analysis literature
> (Abeni & Buttazzo 1999 and follow-ups). **I still need to verify the
> exact formulation here against that paper** before trusting it beyond a
> sanity-checked heuristic.

**Budget derivation** (`rq2/procedure/budget.py`), variants:

| variant | samples |
| --- | --- |
| `full` | stressed samples, scaled by `alpha_drift` and `alpha_OS` if applied |
| `no_stress` | baseline samples, scaled by `alpha_drift` |
| `no_drift` | stressed samples, unscaled |
| `minimal` | baseline empirical `(1-p)`-quantile only - no model, no factors |

Two routes are reported for each variant/`p`: **Route 1 (direct)** - fit
on that instance's own samples; **Route 2 (reuse)** - baseline samples of
a *new* instance, scaled by `alpha_cores(m) * alpha_OS * alpha_drift`
(useful when you don't want to re-profile every new instance from
scratch). Admission check per core: `sum(Q/T) <= available_fraction`
(configurable, default 0.95).

**Outputs.** `results/derived/budget/budgets.json` (schema in
`docs/data_layout.md`, consumed by `pod_gen.py`'s validation mode) and a
CSV table.

**Implemented by.** `rq2/procedure/cbs_model.py`, `rq2/procedure/budget.py`.
**Status: Batch 2.**

### Optional: replay-based sanity check

`rq2/procedure/replay.py` predicts misses on a measured sequence under a
candidate `Q`, skip semantics (`n = ceil(C/Q)`; `n>1` misses that job and
skips the next `n-1`), and reports `(m,k)` for `k in {50,100}` and max
consecutive misses, reusing `rq2/common/metrics.py`. **Status: Batch 2.**

## Step 5 - Validation under KubeDeadline

**Purpose.** Run the derived budgets for real (`configs/campaign_validation.yaml`,
`--overrun continue`) and check the model's prediction against what
actually happened.

**Per run.** Observed miss rate (skipped counts as missed); predicted
miss probability from the Step 4 model at that `Q`, both i.i.d. and
sequence-based; cluster-based one-sided binomial test of observed vs.
predicted; worst `(m,k)` for `k in {50,100}`; max consecutive misses vs.
the configured burst limit; burstiness; worst lateness in periods
(`(max_response - D) / T`); bandwidth `Q/T`.

**Output.** An ablation table across the Step 4 variants, and a pass/fail
per requirement (rate, burst) - see `rq2/validation/validate.py`.

**Implemented by.** `rq2/orchestration/campaign.py`
(`configs/campaign_validation.yaml`), `rq2/validation/validate.py`.
**Status: Batch 1 (campaign) done, Batch 3 (validate.py) pending.**

## Reporting

Exceedance curves with fits, QQ plots, `alpha_cores(m)` curve, risk(`Q`)
curves with `Q*` marked per `p`, predicted-vs-observed miss rate,
ablation comparison - `rq2/reporting/figures.py` (PDF + PNG). LaTeX
(booktabs) tables for tail bounds, inflation factors, budgets and
validation results - `rq2/reporting/tables.py`. **Status: Batch 3.**
