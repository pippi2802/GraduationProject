# RQ1_final — Claims, Expectations, Results, Metrics

> Two tables for the supervisor: (1) the specific, falsifiable claims RQ1_final is testing,
> each with a stated expectation, the actual result, and its magnitude; (2) the metric
> definitions used to test them and why each one exists. Numbers below are from
> `analysis/analysis.ipynb` as of 2026-09-09 (model3's four combinations + model1 baseline;
> model1/model4 final rounds and the flagged sib-cfs anomaly check still pending
> confirmation — treat magnitudes here as provisional until that's closed).

## Table 1 — Claims, Expectations, Results

| # | Claim | Expectation | Result | Magnitude |
|---|---|---|---|---|
| 1 | A KubeDeadline reservation alone (no interference) delivers close-to-promised response time. | `R` tracks `C` closely; deadline misses near zero except at the known measurement noise floor. | **Confirmed.** No systematic deadline misses in the model1 baseline outside the expected low-`U` noise-floor region. | Deadline-miss rate ≈0% across the utilization sweep (model1). |
| 2 | Physical-core separation isolates the target from a competitor regardless of the competitor's own scheduling class. | `phys-cfs` ≈ `phys-res` at every `U`, both close to the no-interference baseline. | **Confirmed.** The two track each other almost exactly across the whole sweep, both scales. | Tight scale, U=0.5: normalized R 0.356 (phys-cfs) vs 0.340 (phys-res) — <5% apart. Deadline-miss rate: 0.065% (phys-cfs) vs 0.055% (phys-res) at soft, U=0.1. |
| 3 | SMT-sibling sharing breaks the deadline-miss guarantee, even at low utilization. | `sib-*` shows materially higher deadline-miss rate than `phys-*` at the same `U`, appearing well before the admission ceiling. | **Confirmed.** Misses appear at the very first (lowest) utilization tested. | Soft scale, U=0.1: 25.0% (sib-cfs) / 25.1% (sib-res) deadline-miss rate vs 0.065% / 0.055% for the phys arms — roughly **400× higher**. |
| 4 | The neighbor's own CBS reservation does not protect the target once they share a physical core. | `sib-cfs` ≈ `sib-res` (reservation status of the *neighbor* doesn't matter under SMT sharing), in contrast to how much it matters when the neighbor is un-contained (claim 3). | **Confirmed.** The two sib arms track each other closely, both far above the phys arms. | Soft scale, U=0.1: 25.0% vs 25.1% deadline-miss rate — <1% relative difference between reserved and unreserved neighbor. |
| 5 | The guarantee breaks via execution-time inflation, not via the scheduler withholding promised CPU time (the Δ / dispatch-latency bound). | `dispatch_latency` stays within the paper's Δ = 2(P−Q) bound almost everywhere, in every arm — i.e., admission/scheduling itself doesn't fail even where deadline misses occur. | **Confirmed.** Δ-bound violations are negligible and roughly uniform across all four arms, including the sib arms where deadline misses are common. | Δ-bound violation rate ≤0.035% in every arm/scale/`U` cell — no meaningful difference between phys and sib arms despite the ~400× gap in deadline-miss rate. |
| 6 | Increasing utilization (i.e., less reservation slack) increases mean response time but *decreases* its relative variability. | Mean `R`/`C` grows with `U`; absolute noise (std) stays roughly flat; so CV = std/mean shrinks. | **Confirmed**, model1 baseline. | Soft scale: mean C grows 7.8→64.4ms (U=0.1→0.94, ~8×) while CV falls 0.091→0.035 (~2.6× reduction). Tight scale: CV falls 0.209→0.043 (~5× reduction) over the same range. |
| 7 | A genuine, irreducible noise floor persists in execution time even after full OS-level isolation (core isolation, IRQ steering, frequency pinning). | CV never reaches ~0 even at the least loaded, most isolated cells. | **Confirmed.** | Lowest observed CV: 0.035 (soft, U=0.94); never below this across the full sweep — a real floor, not eliminated by isolation. |

## Table 2 — Metric Definitions

| Metric | Definition | Why it's tracked |
|---|---|---|
| **C** (`C_cputime_us`) | `CLOCK_THREAD_CPUTIME_ID` delta over the compute block — actual CPU time consumed by the job, immune to preemption/steal by construction. | Isolates *compute cost* from scheduling/queueing effects. Distinguishes "the job got slower" (inflated `C`) from "the job got delayed" (inflated `R` with unchanged `C`) — the whole mean-shift vs. delay-bound story (claim 5) depends on this separation. |
| **R** (`R_wall_us`) | Wall-clock `finish − release`. | The end-to-end quantity an application actually cares about; determines whether the deadline was met. |
| **dispatch\_latency** (`dispatch_latency_us`) | `start − release` — time from release to actually starting to execute. | Front-loaded scheduling delay. Directly comparable to the paper's own Δ (worst-case CPU delay) bound — tests whether the *admission/scheduling* guarantee holds, independent of execution-time inflation. |
| **mid\_job\_preempt** (`mid_job_preempt_us`) | `(finish − start) − C` — time elapsed during execution that wasn't spent computing. | Isolates genuine mid-execution scheduling gaps (real preemption/intrusion) from pure IPC slowdown. A large value means the job was actually kicked off the CPU mid-run, not just running slower per instruction. |
| **deadline\_miss / tardiness** | `R > period`; tardiness = `R − period` when missed. | The literal correctness criterion of a real-time guarantee — the metric every other one exists to explain. |
| **CV** (`std/mean`, per cell) | Relative variability of `C` or `R` within a scale/`U` cell. | Normalizes noise magnitude across scales and utilizations so "how noisy is this" is comparable — an absolute µs of noise means very different things at a 1ms mean vs a 60ms mean (claims 6–7 depend on this). |
| **steal\_us** | Guest-visible hypervisor steal time (from `/proc/stat`) over the compute block. | Rules the hypervisor itself in or out as a cause — distinguishes "Azure took our CPU away" from "OS/hardware-level contention on a CPU we actually had." |
| **nonvol\_ctxt** | Involuntary context switches (`ru_nivcsw`) during the job. | Candidate structural cause for noise, tested via partial correlation (controlling for `U`) against `C`'s variability. |
| **normalized\_R** (`R / period`) | `R` expressed as a fraction of the task's own period. | Makes response time comparable across the two different period scales (10ms tight vs 100ms soft) under one unified "≥1 means missed" criterion. |
| **Δ-bound violation** | `dispatch_latency > 2(P − Q)` — the paper's own formal worst-case-delay bound, evaluated per job. | Turns the paper's abstract formal guarantee into a concrete, falsifiable per-job test — the direct empirical check behind claim 5. |
| **α-suspect** (`mid_job_preempt > 5% of Q` while `C < Q`) | A job that stayed under its own compute budget but still experienced a large mid-execution gap. | Proxy for whether the CBS server is actually delivering its promised bandwidth α — distinguishes "ran long because it needed more compute than usual" from "ran long because it wasn't given the CPU time it was promised". |

## Notes for the supervisor conversation

- Every claim above is stated as a falsifiable expectation *before* citing the result, per
  the "explicit experiment model" feedback from the 2026-09-09 meeting.
- Claim 3 vs claim 4 is the pairing that most directly targets the paper's own implicit
  assumption (that a well-behaved, reserved neighbor is a safe neighbor) — worth leading
  with in the discussion.
- Magnitudes for the sib arms (claims 3, 4) are pending the per-round consistency check on
  the flagged tight-scale cells discussed separately; soft-scale numbers used here were
  the more stable of the two and are already round-consistent.
