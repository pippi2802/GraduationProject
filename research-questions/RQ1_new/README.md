# RQ1 (simplified) — where do KubeDeadline guarantees break?

Flat, script-based, in the spirit of `kuberay-test-main`: a **base `job.yaml` you
can read**, a small **`generate_yaml.py`** that stamps it per cell, a **`run_job.sh`**
loop, and a **`result.py`** for the figures. One probe, one CSV schema, one set of
five figures — a model is just its `job.yaml` + `config.yaml`.

No canary, no cloud-factor attribution: the question is *where the guarantee breaks*,
so we keep only the guarantee metrics (R, C) and their normalized forms.

## Files (all flat at the top)
```
matmul.c  Makefile  Dockerfile  build.sh   the ONE probe (fixed clocks, warm-up, catch-up)
generate_yaml.py    models/<m>/job.yaml + k_table.json -> models/<m>/generated/<scale>/U<u>.yaml
run_job.sh          loop the generated manifests: create -> wait -> pull jobs.csv -> delete
calibrate.py        K per (scale,U) so median C ≈ 0.7·Q  (run with frequency PINNED)
result.py           the five figures + results/<m>/summary.csv  (pandas/matplotlib)
node-prep/apply.sh  node agent: PIN CPU FREQUENCY + expose results
models/
  model1/{config.yaml, job.yaml}   clean baseline
  model2/{config.yaml, job.yaml}   + reserved neighbours    (co_runners.neighbours)
  model3/{config.yaml, job.yaml}   + SMT-sibling interferer (co_runners.interferer)
  model4/{config.yaml, job.yaml}   IRQ steering (node action; run twice off/on)
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

## Run a model (e.g. model2, both scales)
```bash
# 0. build + push the probe once (any model uses it)
IMAGE=pippina2/rq1-probe:v1 ./build.sh

# 1. pin frequency + start the results agent on the model's node
node-prep/apply.sh model2

# 2. calibrate K at the pinned clock (native on an isolated core, or via a pod)
python calibrate.py model2 --local        # -> models/model2/k_table.json

# 3. stamp the manifests, then run + plot
python generate_yaml.py model2            # -> models/model2/generated/<scale>/U<u>.yaml
./run_job.sh model2                        # both scales (or: ./run_job.sh model2 soft)
python result.py model2                    # -> results/model2/summary.csv + figures/
```

Model 4 (IRQ off vs on): steer IRQs away, run the sweep, move `results/model4` →
`results/model4-off`; steer onto the core, run again → `results/model4-on`; compare.

## Reproducibility (built in)
- **Frequency pinned** (`node-prep`) so `C` is a stable base-clock measurement.
- **Headroom** (`C ≈ 0.7·Q`) so R stays bounded, not divergent.
- **Fixed probe** (fixed seed, fixed K), off-schedule **warm-up** + missed-release
  **catch-up** so a slow start can't poison a run.
- **Calibration recorded** per model (`models/<model>/k_table.json`).
