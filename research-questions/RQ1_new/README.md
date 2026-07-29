# RQ1 (simplified) — where do KubeDeadline guarantees break?

Flat, script-based, in the spirit of `kuberay-test-main`: a **base `job.yaml` you
can read**, a small **`generate_yaml.py`** that stamps it per cell, a **`run_job.sh`**
loop, and a **`result.py`** for the figures. One probe, one CSV schema, one set of
five figures — a model is just its `job.yaml` + `config.yaml`.

No canary, no cloud-factor attribution: the question is *where the guarantee breaks*,
so we keep only the guarantee metrics (R, C) and their normalized forms.

## Files (all flat at the top)
```
matmul.c  Makefile  Dockerfile  build.sh   the ONE probe: --kind matmul (FP) | ptrchase (memory/LLC)
generate_yaml.py    models/<m>/job.yaml + k_table.json -> models/<m>/generated/<scale>/U<u>.yaml
run_job.sh          loop the generated manifests: create -> wait -> pull jobs.csv -> delete
calibrate.py        K per (scale,U) so median C ≈ 0.7·Q  (run with frequency PINNED)
result.py           the five figures + results/<m>/summary.csv  (also: result.py compare A B)
node-prep/apply.sh  node agent: PIN CPU FREQUENCY + expose results
node-prep/steer-irqs.sh  model4: steer device IRQs off/onto the RT core (+ /proc/interrupts evidence)
models/
  model1/{config.yaml, job.yaml}   clean baseline
  model2/{config.yaml, job.yaml}   + reserved neighbours    (co_runners.neighbours)
  model3/{config.yaml, job.yaml}   + interferer, SMT sibling OR separate core (INTF_PLACEMENT)
  model4/{config.yaml, job.yaml}   IRQ steering off/on       (IRQ_STEER)
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
figures are directly comparable across models.

## Run a model
```bash
# 0. build + push the probe once (rebuild after editing matmul.c; bumps to :v2)
./build.sh

# 1. pin frequency + start the results agent on the model's node
bash node-prep/apply.sh model2

# 2. calibrate K (pinned clock)  3. stamp manifests  4. run  5. plot
python calibrate.py model2                  # -> models/model2/k_table.json
python generate_yaml.py model2              # -> models/model2/generated/<scale>/U<u>.yaml
./run_job.sh model2                          # both scales (or: ./run_job.sh model2 soft)
python result.py model2                      # -> results/model2/summary.csv + figures/
```

### Choose the workload (any model)
`matmul` (default, FP/in-cache) or `ptrchase` (memory/LLC-bound). Set `WORKLOAD` for
calibrate **and** generate: it uses a separate `k_table.<kind>.json` and injects the
kernel into every probe (target + co-runners). Keep results apart with `OUT_TAG`:
```bash
WORKLOAD=ptrchase BUF_KB=131072 python calibrate.py model3     # 128 MB working set >> LLC
WORKLOAD=ptrchase BUF_KB=131072 python generate_yaml.py model3
OUT_TAG=_mem ./run_job.sh model3                               # -> results/model3_mem/
python result.py model3_mem
```

### model3 — interferer placement (SMT sibling vs separate core)
```bash
INTF_PLACEMENT=sibling  ./run_job.sh model3                    # same physical core (default)
INTF_PLACEMENT=separate OUT_TAG=_sep ./run_job.sh model3       # control: different core
python result.py compare model3 model3_sep                     # overlay CDFs + C-inflation table
```

### model4 — IRQ steering (off vs on)
Real steering + `/proc/interrupts` ground truth (`node-prep/steer-irqs.sh`); each cell
logs `irq.json`:
```bash
IRQ_STEER=off OUT_TAG=_off ./run_job.sh model4
IRQ_STEER=on  OUT_TAG=_on  ./run_job.sh model4
python result.py compare model4_off model4_on
```

**Env knobs:** `WORKLOAD` `BUF_KB` (workload) · `INTF_PLACEMENT` (model3) · `IRQ_STEER`
(model4) · `PIN_RTCPU` (force the target onto a fixed logical cpu, e.g. `PIN_RTCPU=0`,
via placement retries) · `OUT_TAG` (results subdir suffix, e.g. `_sep` → `results/<model>_sep/`).

## Reproducibility (built in)
- **Frequency pinned** (`node-prep`) so `C` is a stable base-clock measurement.
- **Headroom** (`C ≈ 0.7·Q`) so R stays bounded, not divergent.
- **Fixed probe** (fixed seed, fixed K), off-schedule **warm-up** + missed-release
  **catch-up** so a slow start can't poison a run.
- **Calibration recorded** per model (`models/<model>/k_table.json`).
