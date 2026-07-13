# Model 1_1 — Deterministic clean-baseline RT experiment (KubeDeadline / RQ1)

A self-contained harness that measures the **irreducible virtualization noise floor**
of a KubeDeadline (rt-DRA) reservation on AKS, using a **deterministic** matrix-multiply
probe and a **two-clock delay decomposition**.

> **Why not rt-app (like `../model1`)?** rt-app's per-loop work has intrinsic jitter that
> pollutes the delay signal. Here the inner task runs a **fixed** dense `M×M` double
> matmul (fixed data, fixed seed, `K` reps/job), so *any* variance in the measured
> times is the **cloud environment's** signature, not workload noise.

## The measurement

Each job records two clocks:

| symbol | clock | meaning |
| ------ | ----- | ------- |
| `C` | `CLOCK_THREAD_CPUTIME_ID` | CPU time the RT thread actually consumed (execution layer) |
| `R` | `CLOCK_MONOTONIC` | wall time release→finish (the guarantee) |

The thesis fits, offline, the additive attribution identity:

```
R − C  ≈  I_steal + I_IRQ + I_preempt + Δ_server + ε
```

`R − C` is further split per job into **dispatch latency** (`start − release`, front-loaded
CBS/scheduler timing) and **mid-job preemption** (`(finish − start) − C`, intrusion during
the job).

`K` is **calibrated per cell** so that median `C ≈ Q = round(U·P)` — the probe demands
exactly its reservation, so a miss means the *environment* failed to deliver bandwidth.

## Grid

- Scales: **tight** `P = 10 ms`, **soft** `P = 100 ms`.
- Utilization `U ∈ {0.1 … 0.9, 0.94}` (0.95+ is refused admission by the rt-DRA driver).
- `m = 1` core per container, one SCHED_FIFO task.
- `N = 5000` measured jobs (+200 warmup) per cell.

Everything is driven by [config.yaml](config.yaml) — the single source of truth.

## Layout

```
config.yaml            all parameters (DRY)
model1lib.py           shared derivations (Q, K, cell grid, names, paths)
calibration/           calibrate.py -> k_table.json  (K per cell so median C ≈ Q; model2/3/4 REUSE it)
manifests/template/    RtClaimParameters + ResourceClaimTemplate + Pod (render.py)
node-prep/             detect-only topology mapping DaemonSet (NEVER offlines a vCPU)
parse/                 thin shims over common/rtmetrics (join_covariates.py, supply.py)
run_model1.py          orchestrator: calibrate -> canary -> sequential sweep -> collect
analyze.py             offline reduction (uses common/rtmetrics): join + supply + tail-summary.csv
plots/                 plot_all.py -> figures/ (common.py = shim over common/rtmetrics.plotting)
```

> **Shared code lives in [`../common`](../common):** the workload
> (`common/kernel`, image `pippina2/model1-kernel:v0.1.0`), the sampler
> (`common/sampler`) and the metrics-analysis library (`common/rtmetrics`).
> model1_1 / model2 / model3 / model4 all use it; **model1 is independent**.

## Prerequisites

- A node labelled `experiment-model=model1` (`kubectl label node <n> experiment-model=model1`).
- The rt-DRA driver installed (ns `dra-rt-driver`, `*.example.com` API), as in `../model1`.
- `kubectl` context pointing at the rt-cluster (run from `rt-cluster-cp-0`).
- Docker Hub login for building the kernel image.

## Run it

**1. Build + push the kernel image** (once):

```bash
docker login                 # Docker Hub, namespace pippina2
../common/kernel/build.sh    # builds pippina2/model1-kernel:v0.1.0 and pushes (SHARED)
```

**2. Apply the node-prep + sampler DaemonSets**:

```bash
node-prep/apply.sh                                  # detect-only cpu-map.json (offlines nothing)
../common/sampler/apply.sh model1-1 model1_1 model1 # shared sampler -> /var/lib/model1_1/samples
```

**3. Calibrate `K`** (median `C ≈ Q`, on an isolated core):

```bash
python calibration/calibrate.py       # writes calibration/k_table.json (+ cv_report, k_curve)
```

Fails loudly (exit 3) if the isolated-core CV exceeds `kernel.cv_threshold` (2%) — a clean
`C` is a precondition for delay attribution.

**4. Sweep a time-block**:

```bash
python run_model1.py --timeblock tb-$(date +%Y%m%d-%H%M)
```

The orchestrator runs calibration automatically if `k_table.json` is missing, starts the
continuous canary, then sweeps both scales × the `U` grid **sequentially**. Per cell it
retries placement until the RT `RT_CPUSET` is Ready **and disjoint from the canary's real
SMT-sibling core** (the driver is SMT-blind), waits for the probe pod to **Complete**
(matmul self-terminates after `N` jobs) under a wall-cap, then copies `jobs.csv` +
`cell.json`. Covariate streams are copied once at the end.

Useful flags: `--scales tight`, `--only-u 0.5 0.94`, `--dry-run`, `--skip-calibration`.

**5. Analyze + plot**:

```bash
python analyze.py  --timeblock tb-YYYYMMDD-HHMM   # join covariates + supply + tail-summary.csv
python plots/plot_all.py --timeblock tb-YYYYMMDD-HHMM
```

## Results layout

```
results/<timeblock>/
  <scale>/U<u>/jobs.csv                    per-job C, R, delay, dispatch, mid-job preempt, miss
  <scale>/U<u>/jobs_with_covariates.csv    + steal/IRQ/softirq/server usage joined per window
  <scale>/U<u>/cell.json                   full provenance (P,Q,U,K,M,rt_cpuset,canary_core,node,kernel,...)
  samples/{cpu,tasks,server}.csv           continuous covariate streams (CLOCK_MONOTONIC)
  tail-summary.csv                         one row per cell (percentiles, miss rate, alpha_eff, Delta_eff)
  figures/*.png                            fig1..fig9
```

## Figures

| file | content |
| ---- | ------- |
| `fig1_R_ccdf_<scale>` | response-time CCDF, one curve per `U` |
| `fig2_C_vs_R_<scale>` | compute `C` vs wall `R` (p50 + p99) vs `U` |
| `fig3_R_percentiles_<scale>` | `R` p50/p99/p99.9/max vs `U` |
| `fig4_cross_scale` | tight vs soft `R` p99 vs `U` |
| `fig5_supply_<scale>` | `alpha_eff` & `Delta_eff` vs `U` with theory lines `α=Q/P`, `Δ=2(P−Q)` |
| `fig6_miss_tardiness` | deadline-miss rate + max tardiness vs `U` |
| `fig7_covariate_scatter` | per-job `R−C` vs `steal+IRQ` (attribution check) |
| `fig8_timeseries_<scale>_U<u>` | `R` and steal/IRQ over job index for the busiest cell |
| `fig9_calibration_curve` | `K` vs median `C` (calibration linearity) |

## Hard-won caveats baked into this harness

- **Never offline a vCPU on D4s_v5** — it wedges the VM and zeroes the RT budget chain.
  node-prep is **detect-only**; isolation is guaranteed by placement-retry + auditing
  `rt_cpuset` vs `canary_core` per cell.
- **`U ≥ 0.95` is unschedulable** (driver admits only `reqUtil < 950‰`); ceiling is `0.94`.
- **Read counters via the sampler pod**, never `kubectl exec` into the FIFO-90 cell — a
  saturated core starves the exec and hangs.
- **Divergent high-`U` tails are unbounded** — report them as *diverges*, not fixed values;
  plots use linear axes with divergent cells annotated.
