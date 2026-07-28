# FINDING — Model 1_1: response time diverges while execution time stays flat

**Where:** `research-questions/RQ1/model1_1`, time-block `tb-20260714-1449`
**Status:** root-caused; fix applied (calibration headroom + CPU-frequency pinning).

---

## Symptom

In every figure the compute clock **C is flat and small** while the wall-clock
response time **R explodes and zig-zags** across utilisation:

- `fig2_C_vs_R_*`: `C p50` (green) sits on ~0 on an axis that runs to 300,000 ms;
  `R p50`/`R p99` jump between a few seconds and ~296 s with no relation to U.
- `fig3_R_percentiles_*`, `fig4_cross_scale`: the same non-monotone spikes.
- `fig5_supply_*`: `alpha_eff` reaches 1.5 (impossible for a single core) and
  `Delta_eff` mirrors R.
- `miss_rate = 1.0` in essentially every cell (100 % of jobs miss the deadline).

So the problem is **not** in the execution layer. The compute kernel is clean;
all of the magnitude is in the **delay** layer `R − C`.

## Evidence: the delay is backlog, not interference

`R − C` splits into `dispatch_latency` (start − release) and `mid_job_preempt`
(interruption *during* compute). In `tail-summary.csv` these are wildly different:

| soft cell | R_p50 | dispatch_max | midpreempt_max |
|-----------|-------|--------------|----------------|
| U0.3      | 2.6 s | 4.7 s        | 141 ms         |
| U0.5      | 154 s | 296 s        | 101 ms         |

~99.97 % of the delay is **dispatch latency**: jobs start progressively later and
later, while the time actually lost *inside* a job (steal/IRQ/preemption) is only
tens to ~100 ms. That is the fingerprint of a **growing queue backlog**, i.e. the
task is being released faster than it can be served — not external interference
during compute.

## Mechanism

The reservation was calibrated so that per-job compute demand `C ≈ Q` (the budget)
— **zero headroom**. A server whose demand equals its supply (utilisation
`rho = C/Q ≈ 1`) is *critically loaded*: any residual gets queued and never drains.
The kernel's periodic loop advances the release clock by exactly one period each
iteration (`next_ns += period_ns`), so every period the job cannot finish is added
to a **permanent** backlog; releases pile into the past, `start − release` ramps to
the length of the whole run, and

```
R_median  ≈  (N/2) · P · (C − Q) / Q
```

Plugging in soft U0.5 (C≈78 ms, Q=50 ms, P=100 ms, N=5000) → ~142 s, matching the
observed 154 s. Even the "clean" cells (U0.3/0.6/0.7, where C≈Q to within 0.5 %)
drift to a few seconds, because at `rho≈1` the queue still creeps upward.

### Why the spikes / heterogeneity between cells

Comparing calibration (`k_table.json`) against the run (`C_p50`), the execution
time was inflated by a **bimodal factor**: cells landed at either `C_run ≈ C_calib`
(ratio ≈ 1.00: U0.3/0.6/0.7) or `C_run ≈ 1.55 · C_calib` (U0.2/0.4/0.5/0.8/0.9/0.94).
Because `C` counts only on-CPU time, only **CPU frequency** (turbo vs base P-state)
can cause this — calibration ran on an isolated/turbo core, while during the sweep
the node also carried the canary + sampler + noisy neighbours, so turbo was often
not granted. Each cell (a separate, sequential pod) drew its own turbo/base outcome.
That 1.55× swing is the **trigger** that decides how far each cell overshoots Q,
hence the apparently random spikes — but the *magnitude* of R is pure backlog, not
the frequency swing itself.

### fig5 supply is not trustworthy here

`alpha_eff > 1` is unphysical for a 1-core reservation. It is an artefact of
computing effective supply over the **diverged** `[first_release, last_finish]`
window; `Delta_eff` likewise just re-plots the dispatch backlog. Once the run no
longer diverges these become meaningful again.

## Resolution

Two changes make the environment stable (both applied):

1. **Calibration headroom** — `config.yaml: calibration.headroom_frac = 0.7`.
   K is now tuned so `median C ≈ 0.7·Q`, so demand is safely below supply
   (`rho ≈ 0.7`). A stable queue drains transient bursts, and R settles near
   `C + Delta < P` instead of ramping. This is the primary fix.

2. **CPU frequency pinning** — `node-prep/prepare-node.sh` (`PIN_FREQ=1`) sets the
   `performance` governor and disables turbo (best-effort; recorded as
   `freq_governor`/`turbo` in `cpu-map.json`). This removes the 1.55× C swing so
   the run matches calibration and no cell is pushed over the edge.

### Re-run procedure

```bash
python calibration/calibrate.py --force        # retune K to 0.7·Q
python run_model1.py  --timeblock tb-<new>
python analyze.py     --timeblock tb-<new>
```

### Success criteria (stable environment)

- `C_p50 ≈ 0.7·Q`, and `C_p50 / Q < 0.9` for every cell (`rho_C_over_Q` in
  `tail-summary.csv`; `diverged = false`).
- `R_p50` slightly above `C`, well under `P`; `R` monotone/smooth vs U.
- `miss_rate ≈ 0`; `dispatch_max` on the order of `Delta = 2(P−Q)`, not seconds.
- `alpha_eff ≤ alpha`.
