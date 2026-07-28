# What "the sweep" is — and why a cell behaves differently alone vs. in the sweep

**Audience:** anyone reading the RQ1 results who wonders why the same experiment
cell looks clean when run by hand but noisy/divergent inside the automated run.

---

## 1. Vocabulary

Think of an experiment as filling in a **table of measurements**. Each knob is one
dimension of the table:

| knob | values |
|------|--------|
| **scale** | tight (P = 10 ms), soft (P = 100 ms) |
| **utilization U** | 0.1, 0.2, … 0.9, 0.94 |
| **k** (model2 only) | 1, 2, 4, 8 tasks sharing one reservation |
| **split** (model2 only) | equal, victim/greedy |
| **arm** (model3/4) | physical/sibling, off/on |

- **Cell** = one fully-specified combination = one row of the table
  (e.g. `tight, U=0.8, k=8, equal`). One cell = one pod (or pod set) launched,
  run for `N` jobs, measured, then deleted.
- **Grid** = every cell (all combinations of the knobs).
- **Sweep** = the program (`run_modelN.py`) that walks the grid and measures each
  cell, **one after another**, in a single invocation.

"Sweep" is the standard experimental-science term for *systematically varying
parameters across their range and recording the output at each setting.*

## 2. What the sweep loop does

```
for each cell in the grid:          # THE SWEEP
    render the pod manifest for this cell
    kubectl apply                   # start it
    wait until scheduled / Ready
    wait until the probe finishes its N jobs
    copy the result CSVs off the node
    kubectl delete                  # tear it down
    settle a few seconds -> next cell
```

One command produces the whole table (~20–60 rows for model2).

## 3. Why "alone" ≠ "inside the sweep"

The **cell parameters are identical** either way (same U, k, K reps). What changes
is the **state of the node at the moment the cell runs**:

```
RUN ALONE                          INSIDE THE SWEEP
──────────                         ────────────────
node is idle                       sampler + node-prep + kubelet busy,
                                   previous pods tearing down, co-tenants running
   |                                  |
   v                                  v
CPU grants TURBO                   CPU stays at BASE freq (turbo denied under load)
   |                                  |
   v                                  v
matmul runs fast -> C ≈ Q          same matmul ~1.5x slower -> C > Q
   |                                  |
   v                                  v
bounded R (meets deadline)         backlog grows -> R explodes, miss_rate = 1.0
```

Two environmental variables move between the two conditions:

1. **CPU frequency (turbo / P-state).** Calibration and single-cell runs happen on
   an *idle* core, which gets turbo, so `C ≈ Q`. During the sweep the node also
   carries the sampler, node-prep, pod churn and (for intra/inter) co-tenants, so
   turbo is often **not** granted and the *same* matmul takes ~1.5× longer.
2. **Core placement.** The rt-DRA driver is SMT-blind and worst-fits onto a random
   *logical* CPU, so a swept cell may share a physical core with a hyper-thread
   sibling; a single manual run usually lands on a clean core.

## 4. Why a small `C` change causes a huge `R` change

The probe is calibrated so per-job compute demand `C ≈ Q` (the budget) — **zero
headroom**. Response time then follows:

```
R_median  ≈  (N / 2) · P · (C − Q) / Q
```

`R` depends on the **sign of `C − Q`**, not its size:

- `C` just **below** `Q`  → bounded `R` (≈ P), deadlines met.
- `C` just **above** `Q`  → the backlog grows every period and never drains →
  `R` climbs into tens/hundreds of seconds, `miss_rate = 1.0`.

So the ~1.5× turbo swing (and integer-`K` rounding at the tight scale, where `K` is
tiny) pushes each cell across the `C = Q` cliff almost at random — which is exactly
the non-monotone scatter seen across the swept results (e.g. tight `U=0.8`: `k=8`
bounded at ~1 ms while `k=4` diverges to ~2 s).

## 5. The analogy

Timing a drive:

- **Alone** = 3 a.m. on an empty road → fast, consistent.
- **Sweep** = the same route during rush hour → traffic (other cells, samplers, CPU
  throttling) makes each run slower and more variable.

The route (cell parameters) didn't change; the **conditions during the batch** did.
Measuring under load is what we *want* — we just have to hold the frequency fixed so
it's a fair comparison, and give the probe a little slack so a bit of "traffic"
doesn't make the trip effectively infinite.

## 6. It is NOT caused by Python, and NOT fixed by parallelism

- The variability is **environmental** (frequency + placement changing under sweep
  load), amplified by the zero-headroom probe. The orchestration logic is not
  injecting randomness.
- The sweep already uses parallelism **where it belongs**: cells run *sequentially*,
  but the tasks *inside* a cell run concurrently (that concurrency is the variable
  being measured). Running cells in parallel (e.g. with Ray) would **worsen** this —
  more concurrent load → less turbo, more SMT contention — and destroy the
  controlled isolation the experiment depends on. Ray-style parallelism suits
  throughput/ML workloads; this is an isolation / real-time-guarantee experiment.

## 7. The validity principle

RQ1 rests on one idea you already hold: **a deterministic constant-work probe means
all variance is the environment's signature.** The sweep exposed the catch —
**"the environment" must mean the *cloud*, not your harness.** So the method is:

> **control the confounds you own, measure the covariates you don't, and treat only
> the residual as the phenomenon.**

## 8. Control what the harness introduces (eliminate — don't measure)

- **Pin CPU frequency** (disable turbo, `performance` governor). The single most
  important change — it removes the self-induced turbo confound. **Non-negotiable.**
- **Fix / log the cpuset + SMT sibling per cell**, so model3's placement factor does
  not leak into every other model's variance as hidden noise.
- **Standardize node state between cells**: settle time, drain teardown, verify no
  prior-cell pod is still running before starting the next. The goal: *"inside the
  sweep" should equal "alone" except for the cloud's own behaviour.*

## 9. Keep a controlled knob instead of engineering the phenomenon away

The headroom fix (`C = f·Q`) is right for stability, but a *fixed* `f = 0.8` hides
the `C → R` amplification you may actually want to observe. So make `f` a **swept
input**, not a hard-coded constant:

| `f = C/Q` | regime | use |
|-----------|--------|-----|
| 0.8 | clean, bounded-R | attribution — steal/IRQ correlations are readable |
| 0.95 | near the edge | transition |
| ~1.0 | sensitivity / fragility | "how close to the cliff does the cloud push me?" |

That turns the cliff behaviour into a **measured output**, not something you designed
away.

## 10. Measure the covariates you cannot control (attribution)

Log **steal time**, **IRQ/softirq CPU-time**, and **`freq_khz`** per cell / per job.
These are your clean measured signals. A valid finding = **a variance component you
can positively correlate with one of these**, not just an unexplained blob.

## 11. Control temporal / tenant confounds (design, not code)

- **Randomize cell order** within the sweep — if `U` always ascends, thermal/tenant
  drift *aliases* onto `U` and masquerades as a utilization effect.
- **Randomized block design + always-on canary + ≥ week-long replication**, so
  time-of-day tenant contention is averaged/blocked, not baked into one cell's
  single draw.

## 12. Then — and only then — interpret the residual

After you have pinned frequency and regressed out steal/IRQ, whatever variance
**remains and cannot be attributed** is your genuine RQ1 evidence of cloud
non-determinism. A large unattributable residual is a *finding* **once the
controllable confounds are closed** — before that, it is just apparatus noise.

## 13. Validity checklist — a cell only "counts" if:

1. **Frequency pinned** and `freq_khz` logged (proves the harness didn't cause the
   `C` swing).
2. **cpuset + SMT sibling logged** (placement controlled / auditable).
3. **steal + IRQ logged** (covariates available for attribution).
4. **Cell order randomized + canary running** (temporal confound controlled).
5. **Replicated across ≥ a week** (not a single-shot draw).
6. The claim about the cell is backed by **either a controlled knob (`f`) or a
   measured covariate** — never by unexplained scatter alone.
