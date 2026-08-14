# RQ1 (simplified) — where do KubeDeadline guarantees break?

Flat, script-based, in the spirit of `kuberay-test-main`: a **base `job.yaml` you
can read**, a small **`generate_yaml.py`** that stamps it per cell, a **`run_job.sh`**
loop, and a **`result.py`** for the figures. One probe, one CSV schema, one set of
five figures — a model is just its `job.yaml` + `config.yaml`.

No canary, no cloud-factor attribution: the question is *where the guarantee breaks*,
so we keep only the guarantee metrics (R, C) and their normalized forms.

## Files (all flat at the top)
```
matmul.c  Makefile  Dockerfile  build.sh   the ONE probe: --kind matmul (FP) | primes (data-dependent)
generate_yaml.py    models/<m>/job.yaml + k_table.json -> models/<m>/generated/<scale>/U<u>.yaml
run_job.sh          loop the generated manifests: create -> validate placement -> wait ->
                     pull jobs.csv -> validate row count -> delete (auto-retries + reports failures)
calibrate.py        K per (scale,U) so median C ≈ 0.7·Q  (run with frequency PINNED)
result.py           the five figures + results/<m>/summary.csv + [sanity] warnings
                     (also: result.py compare A B)
node-prep/apply.sh    node agent: PIN CPU FREQUENCY + expose results
node-prep/isolate.sh  isolcpus/nohz_full/rcu_nocbs on the node (stages it; reboot is manual)
node-prep/steer-irqs.sh  model4: steer device IRQs off/onto the RT core (+ /proc/interrupts evidence)
models/
  model1/{config.yaml, job.yaml}   clean baseline
  model2/{config.yaml, job.yaml}   target m=1 + one reserved neighbour m=1, forced same physical core
  model3/{config.yaml, job.yaml}   target m=2, PAIR_TYPE x COMPETITOR_TYPE 2x2 sweep
  model4/{config.yaml, job.yaml}   IRQ steering off/on (IRQ_STEER) — parked for now
results/<model>/<scale>/U<u>/jobs.csv · <model>/summary.csv · <model>/figures/
```

`config.yaml` = the sweep grid + calibration knobs (+ co-runners). `job.yaml` = the
readable manifest with five tokens `generate_yaml.py` fills:
`@@NAME@@ @@RUNTIME@@(Q) @@PERIOD@@(P) @@K@@ @@SUB@@`.

## Definitions
| symbol | meaning |
|--------|---------|
| `D = P` | deadline = period |
| `R/D` | normalized response time (`< 1` ⇒ met deadline) |
| `alpha = C/Q` | budget used by compute (`< 1` ⇒ fits budget) |
| `bound = 2(P−Q)` | CBS service-delay bound |
| `Delta = (R−C)/bound` | normalized delay (`< 1` ⇒ within bound) |

## The five figures (per scale, identical for every model)
1. CDF of **R/D** · 2. CDF of **Delta** · 3. CDF of **alpha** · 4. **|R|,|C| vs U**
· 5. **p99 margins vs U** (R/D, alpha, Delta; break line at 1).

Because every model runs the same probe, all `summary.csv` share one schema and the
figures are directly comparable across models. `result.py` also prints `[sanity]`
warnings for cells that look like data-quality problems rather than real phenomena
(short runs, non-monotonic R_p50 vs utilisation) — read these before trusting a sweep.

## Run a model
```bash
# 0. build + push the probe once (rebuild after editing matmul.c; bumps to :v2)
./build.sh

# 1. pin frequency + start the results agent on the model's node
bash node-prep/apply.sh model2

# 1b. (recommended, one-time, needs a reboot) isolate the node's cpus from generic
# Linux housekeeping so the baseline's tail is as clean as possible -- see
# node-prep/README.md. Do this BEFORE calibrating, since it changes timing.
bash node-prep/isolate.sh model2 apply    # stages isolcpus=/nohz_full=/rcu_nocbs=
# <reboot the node yourself>
bash node-prep/isolate.sh model2 status   # confirm it took

# 2. calibrate K (pinned clock)  3. stamp manifests  4. run  5. plot
python calibrate.py model2                  # -> models/model2/k_table.json
python generate_yaml.py model2              # -> models/model2/generated/<scale>/U<u>.yaml
./run_job.sh model2                          # both scales (or: ./run_job.sh model2 soft)
python result.py model2                      # -> results/model2/summary.csv + figures/
```

`run_job.sh` now validates every cell before accepting it (calibration cv, target/
competitor placement, exact row count) and retries automatically up to
`CELL_ATTEMPTS` times; anything still bad after that is listed in a failure summary
printed at the end — check it before treating a sweep as done.

### Choose the workload (any model)
`matmul` (default, FP/in-cache, execution-port-bound) or `primes` (trial-division
primality test over a deterministic candidate stream -- genuinely data-dependent,
early-exit control flow, integer-divide/branch-predictor bound; intrinsic per-job
cv is much higher than matmul's, ~0.1-0.3 rather than ~0.02-0.04 -- pass a looser
`CV_THRESHOLD` when calibrating/running it, see calibrate.py/run_job.sh). Set
`WORKLOAD` for calibrate **and** generate: it uses a separate `k_table.<kind>.json`
and injects the kernel into every probe (target + co-runners). Keep results apart
with `OUT_TAG`:
```bash
CV_THRESHOLD=0.3 WORKLOAD=primes python calibrate.py model3
WORKLOAD=primes python generate_yaml.py model3
CV_THRESHOLD=0.3 OUT_TAG=_primes ./run_job.sh model3           # -> results/model3_primes/
python result.py model3_primes
```

### model2 — two containers, one physical core
Target (m=1) + one reserved neighbour (m=1). The neighbour is placed and
confirmed **Ready before the target is even created** — the target is then
forced onto the neighbour's actual SMT sibling (retried until true). This
ordering matters: bundling them together and letting the target start as soon
as it's up was tried first and confirmed unreliable in practice (cells where
the target had no real contention because the neighbour wasn't running yet, or
had a placement window before it started). Confirmed placement is logged in
`placement.json`. Compare against `model1` (no neighbour) as the control:
```bash
./run_job.sh model2
python result.py model2
python result.py compare model2 model1     # C-inflation of a shared-core reserved neighbour
```

### model3 — m=2 reservation: pair_type x competitor_type (2x2 sweep)
The target's own reservation spans 2 cpus (`RtClaimParameters.count: 2`); the probe
still pins to only the first one (no probe code changes). `PAIR_TYPE` controls
whether that pair is two SMT threads of one physical core (`sibling`) or one thread
from each of two different physical cores (`physical`); `COMPETITOR_TYPE` controls
what occupies the pair's spare cpu. `run_job.sh` reads real topology from
`/sys/.../topology/thread_siblings_list` and retries placement (up to
`CELL_ATTEMPTS`) until both match — logged in `placement.json`.
```bash
PAIR_TYPE=sibling  COMPETITOR_TYPE=unreserved OUT_TAG=_sib_cfs  ./run_job.sh model3
PAIR_TYPE=sibling  COMPETITOR_TYPE=reserved   OUT_TAG=_sib_res  ./run_job.sh model3
PAIR_TYPE=physical COMPETITOR_TYPE=unreserved OUT_TAG=_phys_cfs ./run_job.sh model3
PAIR_TYPE=physical COMPETITOR_TYPE=reserved   OUT_TAG=_phys_res ./run_job.sh model3
python result.py compare model3_sib_cfs model3_phys_cfs   # HT penalty, unreserved competitor
python result.py compare model3_sib_res model3_phys_res   # HT penalty, reserved competitor
```
Note: the driver is SMT-blind (no "give me a sibling/non-sibling pair" knob), so
`PAIR_TYPE` is achieved by delete/recreate retries, same idea as `PIN_RTCPU`. If a
cell never converges within `CELL_ATTEMPTS`, it's reported as failed rather than
silently accepted with the wrong pairing.

**Fixed in this revision:** `generate_yaml.py` had stopped writing the separate
`_intf/<scale>/U<u>.yaml` file that `run_job.sh` depends on for the unreserved
competitor's placement (a since-reverted fix from an earlier commit) — meaning the
interferer was silently running at a fixed cpu from config instead of the target's
real sibling. This is restored, and the reserved-competitor arm (`_comp/...`) is
new. Any model3 results collected before this fix should be treated as unverified
placement and re-collected.

### model4 — IRQ steering (off vs on) — parked
Real steering + `/proc/interrupts` ground truth (`node-prep/steer-irqs.sh`); each cell
logs `irq.json`. Deprioritized for now (the `off`-arm ground truth is likely
dominated by non-steerable per-cpu housekeeping interrupts, not device IRQs, and the
`on` arm was never completed) — revisit after model2/model3 are solid:
```bash
IRQ_STEER=off OUT_TAG=_off ./run_job.sh model4
IRQ_STEER=on  OUT_TAG=_on  ./run_job.sh model4
python result.py compare model4_off model4_on
```

**Env knobs:** `WORKLOAD` `BUF_KB` (workload) · `PAIR_TYPE` `COMPETITOR_TYPE`
(model3) · `IRQ_STEER` (model4) · `PIN_RTCPU` (force the target's first cpu, e.g.
`PIN_RTCPU=0`) · `PIN_ATTEMPTS` (target placement retries, default 8) ·
`CELL_ATTEMPTS` (whole-cell retries on bad placement/row-count, default 4) ·
`CV_THRESHOLD` (calibration gate, default 0.05 — reflects a measurement-floor
noise investigation on 2026-07-30: short-duration cells, worst for tight-scale
but also soft-scale's own shortest cell (soft-U0.1), sit at cv~0.02-0.04 even
with steal time, SMT-sibling load, and frequency/governor pinning all directly
ruled out as causes; 0.05 clears that floor while still catching genuinely
broken calibrations) ·
`OUT_TAG` (results subdir suffix, e.g. `_sib_cfs` → `results/<model>_sib_cfs/`).

## Reproducibility (built in)
- **Frequency pinned** (`node-prep/apply.sh`) so `C` is a stable base-clock measurement.
- **Core isolation** (`node-prep/isolate.sh`, recommended) so the RT core is free of
  generic Linux housekeeping noise, not just frequency-stable.
- **Headroom** (`C ≈ 0.7·Q`) so R stays bounded, not divergent.
- **Fixed probe** (fixed seed, fixed K), off-schedule **warm-up** + missed-release
  **catch-up** so a slow start can't poison a run.
- **Calibration recorded** per model (`models/<model>/k_table.json`), and gated:
  `run_job.sh` refuses to run a cell whose recorded cv exceeds `CV_THRESHOLD`.
- **Placement verified, not assumed**: every cell's actual co-location (or lack of
  it) is read from real topology/`RT_CPUSET` and retried until it matches the
  model's design, logged in `placement.json`.
- **Row count validated**: a cell only counts as collected if `jobs.csv` has exactly
  the expected number of rows; short cells are retried automatically and any that
  still fail are listed in the end-of-run summary.
