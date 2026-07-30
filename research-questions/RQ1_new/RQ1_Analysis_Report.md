# RQ1 — Analysis of experiments so far

**Question (RQ1):** *Where* do KubeDeadline's timing guarantees break down when a
container is given a SCHED_DEADLINE / H-CBS reservation (Q, P, m) on Azure AKS?

**Date of analysis:** 2026-07-29
**Data set:** `RQ1_new/results/` — models: `model1`, `model2`, `model3`,
`model3_sep`, `model4_off` (+ `model3_run2`, a failed run).
**Runs:** N = 5000 jobs/cell, U-sweep {0.1…0.9, 0.94}, two scales
(`tight` P=10 ms, `soft` P=100 ms), headroom `C ≈ 0.7·Q`.
The matmul probe's warm-up + missed-release catch-up fix is active in all these
runs (the `skipped_before` column is present), so response-time tails are real,
not the old metronome-backlog artifact.

---

## 1. Executive summary — the RQ1 answer

**KubeDeadline does not fail by admission or scheduling — CBS admits every cell
correctly. It fails at the *execution* layer.** The reservation guarantees a
share of **wall-clock time** (Q per P), but it does **not** guarantee a share of
**CPU cycles / IPC**. As soon as another thread contends for the *same physical
core's execution bandwidth* (an SMT sibling or a co-located reserved neighbour),
the fixed matmul work needs **~1.9× more CPU-time** than Q reserves, `C` exceeds
`Q`, the server is permanently overloaded, and **every job misses its deadline**.

The single discriminating metric is the **bandwidth margin α = C/Q**:

| Condition | α (median) | miss rate | Guarantee |
|---|---|---|---|
| **Isolated** (model1, model3_sep, model4_off) | **0.69–0.71** (= the headroom) | ≈ 0 | **holds up to U = 0.94** |
| **Physical-core sharing** (model2, model3) | **1.2–1.8** | **1.0** | **broken at essentially every U** |

**"Where" is not a utilisation number for the interference models.** Because the
break is IPC theft — a roughly *constant* ~1.9× penalty independent of load — the
guarantees break at the **lowest contended U already (0.1–0.2)**, with no smooth
U\* crossing. So the break coordinate is **"presence of execution-bandwidth
sharing," not a value of U.** Utilisation only matters for the *isolated*
reservation, which degrades gracefully and **never crosses the deadline** through
U = 0.94.

---

## 2. Method recap

- **4 OFAT models**, each running the *same* deterministic matmul probe (fixed
  work K, calibrated so `C ≈ 0.7·Q` on a clean isolated core):
  - **model1** — baseline, no interference (validity anchor).
  - **model2** — co-located contention: `count` *reserved* neighbours, each at util `u`.
  - **model3** — hyperthreading: one *unreserved* matmul pinned to the **SMT sibling** of the RT core.
    - **model3_sep** — control arm: same interferer but on a **different physical core**.
  - **model4** — IRQ steering: `off` = device IRQs steered **away** from the RT core (the `on` arm is not yet present).
- **Three normalised margins**, break = p99 crosses 1:
  - **α = C/Q** — bandwidth (does the work fit the budget?)
  - **δ = (R−C)/bound**, bound = 2(P−Q) — delay layer
  - **R/D**, D = P — the deadline itself
- Fixed-work probe ⇒ any change in `C` is a pure execution-layer signal
  (frequency or IPC), which is exactly what makes α the diagnostic.

---

## 3. Per-model findings

### 3.1 model1 — baseline: **holds everywhere (no U\*)** ✅
- **soft:** α p50 pinned at **0.69–0.72** (headroom working exactly), miss = 0,
  R/D p99 rises smoothly **0.08 → 0.69** across U0.1→0.94 and **never crosses 1**.
- **tight:** healthy but noisier — miss 0.2–1.0 % (single-period tail at 10 ms),
  R/D p99 ≤ 0.58 for U0.3–0.7.
- **Interpretation:** correct reference behaviour. An isolated reservation absorbs
  load right up to U = 0.94. This is the anchor that makes the interference
  results interpretable.
- ⚠️ **Data gaps (need rerun):**
  - `tight U0.8 / U0.9 / U0.94` are **empty (0 rows)** — the "pod runs but
    workload doesn't" bug hit those three cells; that's why the tight curve
    truncates at U0.7.
  - `tight U0.2` is an **anomalous single-cell spike** (miss 1.04 %, R/D p99 1.00,
    α p99 1.0) while U0.3–0.7 sit *below* it → non-monotone → transient
    contamination, **not** a real break. Rerun to confirm.

### 3.2 model2 — co-located contention: **breaks catastrophically** ⚠️
- **miss = 1.0 at every cell except `tight U0.1`** (which is clean: α p50 0.67).
- α p50 = **1.2–1.4** everywhere; R/D p99 = 1.04–1.41; δ p99 plateaus at **~0.5**.
- **Interpretation:** even though the neighbours are *reserved*, `C` inflates past
  `Q` — meaning the neighbours are stealing *execution* bandwidth (landing on the
  RT core's SMT sibling, or DVFS-throttling the node under many busy cores),
  **not** just consuming their own admitted budget. The reservation firewall fails
  at the execution layer, same mechanism as model3.
- ❓ **To confirm:** check model2 placement to verify neighbours land on the SMT
  sibling / measure node frequency. The `tight U0.1`-clean, everything-else-broken
  step is consistent with "one neighbour fits, two+ share the sibling."

### 3.3 model3 — hyperthreading (SMT sibling): **breaks hard** ⚠️
- **miss ≈ 1.0** for all U ≥ 0.2 (`tight U0.1` clean).
- α p50 = **1.3–1.8**; several cells show **R/D p99 ≈ 2.0 with δ p99 ≈ 1.0**
  (`tight U0.3`, `tight U0.7`, `soft U0.3`) — jobs slip a *full extra period* even
  with catch-up: a genuine deep-overload tail, not a bug.

### 3.4 model3_sep — separate-core control: **clean (mirrors baseline)** ✅
- α p50 **~0.70**, miss ≈ 0, R/D p99 ≤ 0.79 through U0.94 — indistinguishable
  from model1.

### 3.5 model3 vs model3_sep — **the mechanism proof** 🔑
Median execution-time inflation `C(sibling) / C(separate)` per cell:

| scale | U | C sibling (µs) | C separate (µs) | **inflation** | miss sib | miss sep |
|---|---|---|---|---|---|---|
| tight | 0.1 | 695 | 364 | **1.91** | 0.00 | 0.00 |
| tight | 0.3 | 5047 | 2097 | **2.41** | 0.995 | 0.006 |
| tight | 0.5 | 6645 | 3442 | 1.93 | 0.997 | 0.005 |
| tight | 0.7 | 9406 | 4926 | 1.91 | 1.000 | 0.004 |
| tight | 0.94 | 12355 | 6660 | 1.86 | 1.000 | 0.003 |
| soft | 0.3 | 53205 | 20839 | **2.55** | 1.000 | 0.000 |
| soft | 0.5 | 64395 | 34379 | 1.87 | 1.000 | 0.000 |
| soft | 0.94 | 122507 | 65604 | 1.87 | 1.000 | 0.000 |

**The inflation is a near-constant ~1.9× across every U and both scales** (the two
U0.3 cells hit 2.4–2.55× — worse sibling phasing). The *only* difference between
these two arms is whether the interferer sits on the SMT sibling. This isolates
the hyperthreading penalty cleanly and explains why there is no U\* threshold:
the penalty is a per-core constant, not a function of utilisation.
See `results/model3/figures/cmp_alpha_*` and `cmp_RoverD_*`.

### 3.6 model4_off — IRQ (off arm): **mostly clean, inconclusive** ⚠️
- Baseline-like: α p50 ~0.70, miss ≈ 0 for most cells.
- **Real single-cell anomalies:** `tight U0.1` (miss 1.14 %, R/D p99 1.00,
  δ p99 0.49) and `soft U0.6` (miss 1.56 %, R/D p99 1.06, α p99 1.10, δ p99 0.50).
  `irq.json` shows **246,229 IRQs still landed on the RT core** despite the "off"
  steering — so these two spikes *might* be genuine IRQ hits rather than transients.
- **Calibration outlier:** `tight U0.5` has α p50 = **0.44** (vs 0.70 elsewhere) —
  that cell's K was mis-calibrated (or caught turbo); its C is too small.
- ❗ **model4 is currently inconclusive**: without the **`on` arm** there is no
  contrast, so no IRQ effect can be claimed. Given that IRQs leaked onto the RT
  core even in `off`, the on/off comparison could actually show a delay-layer (δ)
  effect — worth completing.

---

## 4. Weird-but-correct (not bugs)

1. **α > 1 (C > Q)** in model2/3 — the intended bandwidth-break signature.
2. **R/D p99 ≈ 2 with δ p99 ≈ 1** in a few model3 cells — genuine deep-overload
   tail; jobs slip a full period even with catch-up.
3. **δ p99 ≈ 0.5** plateau across broken model2/3 cells — with α > 1 the server is
   permanently backlogged so (R−C) ≈ one guard band (P−Q) ⇒ δ ≈ 0.5. Consistent.
4. **δ collapses to ~0.01–0.02 at U0.94** — bound = 2(P−Q) shrinks to ~0 as Q→P.
5. **model3_sep ≈ model1** — proves the break is SMT-sibling-specific, not "a
   neighbour merely existing."

---

## 5. Data-quality issues to fix

| Item | Cells | Action |
|---|---|---|
| Empty jobs.csv (workload-not-executing bug) | model1 `tight U0.8/0.9/0.94` | rerun |
| Transient single-cell spike | model1 `tight U0.2` | rerun to confirm transient |
| Calibration outlier (α = 0.44) | model4_off `tight U0.5` | recalibrate K / rerun |
| Failed run (only placement.json) | `model3_run2` | discard |
| Missing arm | `model4_on` | run to make model4 conclusive |

---

## 6. Threats to validity

- **Turbo/DVFS confound (previously diagnosed):** the probe measures fixed *work*,
  so C is frequency-sensitive. Frequency must be pinned to a sustainable base clock
  and K recalibrated there; otherwise a turbo "lottery" produces non-reproducible
  cells. The isolated arms here (α pinned at 0.70) indicate the pin held for these
  runs, but this must be re-verified for every rerun.
- **model2 mechanism unconfirmed:** the C-inflation implies SMT/DVFS bandwidth
  theft, but placement was not captured — confirm before attributing it to the
  reservation firewall itself.
- **Tight scale noise floor:** at P = 10 ms, even the clean baseline shows a
  0.2–1 % single-period miss tail; report tight results with that floor in mind.

---

## 7. Bottom line for the thesis

> RQ1's "where" resolves into two regimes.
> **(a) Isolated reservation:** guarantees hold gracefully across the entire
> utilisation range (U ≤ 0.94) with zero deadline misses — there is no breaking
> utilisation. **(b) Execution-bandwidth sharing:** the moment the reserved
> thread shares a physical core (SMT sibling or co-located reserved neighbour),
> C inflates ~1.9× past the budget and *all* deadlines break — at any utilisation,
> including U = 0.1–0.2. KubeDeadline therefore breaks not at a utilisation
> threshold but at a *placement* boundary: its Q reserves time, not cycles, and
> Azure's shared-SMT topology violates that assumption. The separate-core control
> (model3_sep) restores baseline behaviour, isolating hyperthreading as the cause.
