# RQ1_final — Experiment Model per Combination

> For each combination tested: the environment, the workload on each role, the scales/
> utilizations swept, the metrics recorded, and the expected behavior stated up front
> (hypothesis), not narrated after the result. Metric names match `workload.c`'s CSV
> columns directly. Drafted for the 2026-09-09 supervisor discussion on making RQ1's
> experiments explicit rather than implicit.

## Shared across all combinations

- **Target workload**: sieve-of-Eratosthenes probe (`workload.c`), fixed nested loops over
  a fixed bound — deterministic compute cost, no data-dependent branching. Runs under a
  KubeDeadline (H-CBS/CBS) reservation with budget `Q = U × P`.
- **Scales**: `tight` (period 10ms, sieve_n=8192, cache-resident) and `soft` (period 100ms,
  sieve_n≈1M, past this hardware's L2).
- **Utilization sweep**: `U ∈ {0.1, 0.2, ..., 0.9, 0.94}`, both scales.
- **Metrics recorded per job**: `C_cputime_us` (compute actually used), `R_wall_us`
  (end-to-end response time), `dispatch_latency_us` (start − release, front-loaded
  scheduling delay), `mid_job_preempt_us` (mid-execution intrusion), `deadline_miss`,
  `tardiness_us`, `steal_us` (hypervisor steal, sanity check). Derived: measured α (delivered
  bandwidth) and Δ (worst-case delay) vs. the paper's promised α, Δ = 2(P−Q); CV of `R` and
  of `C` per cell.
- **Replication**: 4 rounds per combination, same fixed node, different points in time.

## Combination table

| Combination | Environment (placement) | Competitor workload | Expected behavior (hypothesis) |
|---|---|---|---|
| **model1** (baseline) | Target alone, no competitor | — | Guarantee holds cleanly: `R ≈ C` + small fixed overhead, near-zero deadline misses except at the known short-duration/low-`U` noise floor (irreducible, not a KubeDeadline failure). Reference distribution every other combination is compared against. |
| **model3-phys-cfs** | Target on a **different physical core** than the competitor | Competitor: plain CFS sieve, taskset-pinned, intensity `u=0.4` (unreserved — no CBS admission, can be throttled/preempted by CFS fairness) | Physical-core separation means no shared execution units — expect behavior indistinguishable from model1's baseline across all `U`. If this combination shows any measurable inflation, that's the real finding (something else is leaking across cores, e.g. shared LLC/memory bandwidth, not SMT). |
| **model3-phys-res** | Target on a **different physical core** than the competitor | Competitor: same sieve workload, but under its **own CBS reservation** at `u=0.4` | Same prediction as phys-cfs: physical separation should isolate regardless of the competitor's scheduling class, since the mechanism (if any) at this placement is not SMT pipeline/cache-port sharing. Comparing phys-cfs vs phys-res isolates whether *scheduling class alone* (reserved vs not) matters when there's no shared microarchitecture — expected: no difference between the two. |
| **model3-sib-cfs** | Target on the competitor's **SMT sibling** (same physical core) | Competitor: plain CFS sieve, taskset-pinned, intensity `u=0.4`, unreserved | Guarantee breaks down: expect substantial inflation in `C_cputime_us` itself (mean-shift, not just added delay) — genuine per-instruction slowdown from shared pipeline/cache-port contention, not the scheduler withholding CPU time. Expect `dispatch_latency_us` to stay low (CBS still admits/schedules the target normally) while `C` and downstream `R`/deadline-miss rate blow up, worse as `U` climbs toward the ~0.95 ceiling. |
| **model3-sib-res** | Target on the competitor's **SMT sibling** (same physical core) | Competitor: same sieve workload, but under its **own CBS reservation** at `u=0.4` | Key comparison against sib-cfs: SMT contention is a microarchitectural effect (shared execution ports/cache), not a scheduling-class interaction — expect **similar inflation magnitude to sib-cfs**, i.e. giving the neighbor a CBS reservation does not protect the target, since reservation controls *how much* CPU time the neighbor gets, not *how much it contends per instant while running*. A meaningfully smaller effect here than in sib-cfs would instead suggest the reservation's periodic budget/duty-cycle structure itself reduces contention density — worth flagging explicitly either way, since it directly tests whether "the neighbor is well-behaved" (reserved) is sufficient protection, which is the paper's implicit assumption. |
| **model4** (event vs periodic) | Target alone, no external competitor; internal generator thread on a distinct physical core (`count=2` claim) | — (isolates release/trigger mechanism, not contention) | Isolates dispatch/release-jitter behavior from steady-state contention: compares scheduled (`clock_nanosleep`) release vs. asynchronous event-triggered release. Expect event-triggered activation to show larger/more variable `dispatch_latency_us` than model1's periodic baseline (extra wakeup/scheduling hop through the generator thread and futex-based signaling), while `C_cputime_us` stays unaffected (same compute, only the release mechanism differs). This is the model that answers "time-of-the-effect" (how a task is released) as distinct from "how much interference" (the model3 axis). |

## What this table is for

- Makes explicit, before analysis, which result would be *expected* (physical separation
  protects, SMT sharing breaks guarantees) vs. which result would be *surprising and worth
  digging into* (phys-* showing inflation; sib-res showing meaningfully less inflation than
  sib-cfs).
- The phys-cfs vs phys-res and sib-cfs vs sib-res pairs are the two comparisons that
  isolate "does the neighbor's own reservation status matter" — independent of whether
  the neighbor is on the same physical core or not.
- Ready to bring to the supervisor as the concrete environment/workload/metric/hypothesis
  breakdown requested per experiment.
