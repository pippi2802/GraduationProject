# FINDING — rt-app per-job overhead vs. C = Q at the tight (P=10 ms) scale

**Context:** Model 1 (clean-baseline RQ1) on `rt-cluster-worker-0` (Standard_D4s_v5,
4 vCPU / 2 physical cores), KubeDeadline RT-DRA, rt-app 1.0 (Ubuntu `rt-app` pkg),
one SCHED_FIFO task per (Q,P,m=1) reservation, task **run = Q** so U = Q/P.

**Status:** UNDERSTOOD + MITIGATED. Root cause = the workload generator's fixed
per-job overhead consuming CBS budget on top of the task's compute, which
overloads the reservation only at small Q (tight scale). Mitigation = subtract the
overhead from the busy loop (`rtapp.overhead_us`) so the *container's* total CPU
footprint ≈ Q. Not steal, not jitter, not a KubeDeadline defect.

---

## Symptom

Tight-scale cells (P = 10 ms) with `run = Q` produced **unbounded** response times:
for `tight-U0.2` (Q = 2 ms), `p99.9`/`max` grew linearly with wall-clock, e.g.
3 s → 14 s → 32 s → 68 s → 157 s over ~13 min, never recovering. Soft-scale cells
(P = 100 ms) were healthy (positive slack, bounded R).

## Evidence gathered (on the live `tight-U0.2` pod)

- `cpu.stat: usage_usec` ⇒ container gets **≈ 20 % CPU = exactly Q/P**. The CBS
  **is** delivering its budget (supply is correct).
- `/proc/<tid>/schedstat` run-delay ≈ 80 % of runtime ⇒ the task is throttled for
  ~8 ms of every 10 ms period — normal CBS behaviour at U = 0.2.
- Covariate `steal_jiffies = 0` ⇒ **no visible hypervisor steal** on the RT core.
- Throughput: **completes ≈ 80 jobs/s while jobs arrive at 100/s** (P = 10 ms).
  Using the full 20 % budget while completing 80 jobs/s ⇒ CPU per completed job =
  200000 µs·s⁻¹ / 80 = **2500 µs**, i.e. ~**500 µs more than the nominal 2000 µs**.
- Raw log: the measured `run` phase fills the whole period; `slack` drifts negative
  ~430–500 µs per period (a steady integrator).

## Interpretation

The deficit is **demand-side, not supply-side**. The reservation delivers its
2 ms/10 ms; the *task container* demands ~2.5 ms/10 ms. The extra ~500 µs is
rt-app's **fixed per-job overhead** — timer arm, `clock_gettime`, and the per-loop
log write — which happens *outside* the measured `run` phase but still consumes CBS
budget. With `run = Q` the reservation is loaded to 100 %, so this fixed overhead
tips it over → the queue grows without bound.

Why soft scale is fine: 500 µs against a 40 ms budget is ~1 % (and rt-app's busy
loop slightly under-shoots its request, adding margin), so soft cells stay < Q.

Ruled out:
- **Jitter** — jitter is bounded and mean-reverting; a monotonic, linear,
  13-minute growth is an integrator (a persistent rate deficit), which jitter
  cannot produce.
- **Hypervisor steal / KubeDeadline under-delivery** — `usage = full budget` and
  `steal = 0` show supply is correct; the shortfall is the workload asking for
  more than its budget.

## The methodological tension (C = Q)

The experiment defines **C (task execution time) = Q (budget)**, so U = Q/P is both
the task utilization and the reservation bandwidth. But any real generator adds a
fixed per-job cost, so the *container* demand = C + overhead. There is no way to
have simultaneously (i) busy loop = Q and (ii) container demand ≤ Q. Options:

1. **Compensate:** busy loop = `Q − overhead` ⇒ container demand ≈ Q. "Execution
   time" then includes the harness's fixed cost. Clean, bounded data. *(chosen)*
2. **Reduce the harness overhead** (e.g. lighter/batched logging) so busy = Q keeps
   container demand ≈ Q. Larger change; deferred.
3. **Raise the tight U floor** — accept that at P = 10 ms an irreducible ~0.5 ms of
   runtime overhead makes budgets below a few ms infeasible (matches the original
   config note: "Q < 2 ms hits the VM measurement noise floor").

## Mitigation implemented

`config.yaml → rtapp.overhead_us` (default 0 = no-op). The rt-app generator sizes
the busy loop as `run = max(min_run_us, Q − overhead_us)`. The DRA claim `runtime`
is still Q, so the reservation bandwidth U = Q/P is unchanged; only the busy-loop
compute is reduced to leave room for the harness overhead.

### Validation — `tight-U0.2` with `overhead_us = 700`

| metric | run = Q (before) | run = Q − 700 (after) |
|--------|------------------|-----------------------|
| completion rate | ~80 jobs/s (falling behind) | **~100 jobs/s (keeps up)** |
| p99.9 R | unbounded (→ 157 s) | **flat ~10.7 ms** |
| max R (typical) | unbounded | **~13.7 ms** |
| behaviour | divergent | **bounded** |

This flip on the *same* cell is the definitive proof that the cause was demand
exceeding budget (overhead), not jitter or steal.

## What the corrected data shows (the actual Model-1 signal)

With the reservation no longer self-overloaded, `tight-U0.2` shows:
- a **stable baseline**: `p99.9 ≈ 10.7 ms`, typical `max ≈ 13.7 ms`;
- a **rare tail excursion**: at t ≈ 160 s a burst pushed `max` to **≈ 114 ms**
  (~11 periods) and `p99.9` to ~68 ms, then diluted back down.

That isolated, large excursion against a flat baseline is exactly the
**hypervisor-noise tail** Model 1 is designed to quantify — captured cleanly only
once the generator artifact was removed.

Note: even in the good regime `p99.9 ≈ 10.7 ms` slightly exceeds the 10 ms
deadline, consistent with the CBS worst-case service delay Δ = 2(P − Q) being
comparable to the period at low U — a genuine tight-scale result (see
`parse/supply.py` `Delta_eff`), distinct from the overhead artifact.

## Recommendations for the sweep

- Run with a **measured** `overhead_us` (not an estimate) — measure rt-app's actual
  per-job cost on the node once and set it; it is **per-node** (CPU speed / rt-app
  build dependent).
- Record the actual busy-loop `run_us` alongside `Q_us` in each `cell.json` so the
  compensation is fully captured for reproducibility.
- Document the compensation in the thesis methodology: the reservation is Q = U·P;
  the busy loop is sized to `Q − overhead` so the container's total CPU footprint
  matches the nominal utilization, isolating the measured phenomenon (VM noise/
  steal tail) from the harness's own per-job cost.
- Soft-scale cells are unaffected (overhead ≪ Q); the compensation matters only at
  the tight scale.
