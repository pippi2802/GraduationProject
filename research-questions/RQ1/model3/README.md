# Model 3 — Hyper-thread-vs-physical-core RT experiment (KubeDeadline / RQ1)

The rt-DRA driver admits up to `~0.95 × 4 vCPUs ≈ 3.8` "cores" of reservation, but
a `Standard_D4s_v5` node has only **2 physical cores** (hyper-threaded → 4 logical).
Above `~2.0` aggregate utilisation, work is forced onto hyper-thread **siblings**.
Model 3 asks: when **admitted capacity exceeds physical capacity**, does the
guarantee break as **C-inflation (a provisioning failure — the *same* job runs
*longer* on a contended sibling)** rather than as lost bandwidth?

Model 3 uses the **same** deterministic matrix-multiply probe, the **same** two-clock
delay decomposition, the **same** reused calibration, and the **same** shared
analysis as [`../model1_1`](../model1_1) / [`../model2`](../model2) — a different
node label and a different question.

> **VARIANCE IS THE MEASUREMENT.** The probe (fixed `M×M` double matmul, fixed data,
> `K` reps/job) has near-zero intrinsic variance, so any **execution-time (`C`)**
> inflation under sibling co-location is real contention for shared ALU/FPU/L1/L2
> writing its signature. `C = CLOCK_THREAD_CPUTIME_ID` **advances** under HT
> contention (the same instructions take more cycles), so C-inflation is captured;
> `R − C` is the delay layer. HT interference is **period-independent**, so the
> break should appear at **both** scales with similar **relative** magnitude — the
> cross-scale fingerprint of an execution-layer break.

## The two arms

| arm | flag | what runs | provides |
| --- | ---- | --------- | -------- |
| **physical** (reference) | `--arm physical` | RT task on a **clean physical core**, HT sibling idle (offlined only on non-Azure hw). No interferer. | `C_baseline` (≡ Model 1_1 clean case) |
| **sibling** (treatment) | `--arm sibling` | RT task on one logical CPU + a controlled **interferer** on its **HT sibling** logical CPU | the inflated `C` |

The **same reused `K`** (hence the same reservation) is used for both arms, so
`C(sibling) / C(physical)` is a **pure hyper-thread inflation factor**. The
interferer is an **unreserved**, CFS, `taskset`-pinned matmul whose intensity is the
swept knob `--sibling-load {off,light,medium,saturating}` (default `saturating`) —
CPU-compute only, **no** memory/LLC stressor. See
[manifests/interferer/README.md](manifests/interferer/README.md).

Everything is driven by [config.yaml](config.yaml) — the single source of truth.

## Calibration & kernel & analysis are REUSED (DRY)

- **Calibration**: reuses [`../model1_1/calibration/k_table.json`](../model1_1/calibration/k_table.json)
  (exact grid `K` + `median_C_us` = `C_baseline`). No recalibration.
- **Kernel image**: reuses `pippina2/model1-kernel:v0.1.0` (same `matmul` for RT
  task *and* interferer) — see [`../common/kernel`](../common/kernel).
- **Sampler**: reuses [`../common/sampler/sampler.py`](../common/sampler/sampler.py)
  (per-CPU streams already capture the **sibling core's activity** = the interference
  source).
- **Analysis**: reuses [`../common/rtmetrics`](../common/rtmetrics)
  (`metrics`, `covariates`, `plotting`); Model 3 only adds its own figure set and
  cross-arm C-inflation reduction.

## Layout

```
config.yaml            all parameters (DRY): scales, U grid, arms, interferer, reused calibration/image
model3lib.py           shared derivations (Q, reused K + C_baseline, interferer duty/K, cell grid, names, paths)
node-prep/             detect-siblings.sh (DETECT-ONLY) + offline-sibling.sh (GUARDED) + online-siblings.sh + DaemonSet
manifests/
  template/            rt-cell.template.yaml + render.py (single DRY generator)
  physical/{tight,soft}/   committed rendered RT cells (render.py --all)
  sibling/{tight,soft}/    committed rendered RT cells
  interferer/          interferer.template.yaml (+ committed <scale>-<level>.yaml, placeholder cpu)
run_model3.py          orchestrator: --arm {physical,sibling} [--sibling-load L], sequential sweep, collect
analyze.py             offline reduction (cross-arm): model3-summary.csv + model3-inflation.csv
plots/plot_all.py      figure set -> figures/ (PNG+PDF); reuses ../common/rtmetrics/plotting
results/               git-ignored
```

## Prerequisites

- A node labelled `experiment-model=model3`
  (`kubectl label node <n> experiment-model=model3`).
- The rt-DRA driver installed (`*.example.com` API), as in `../model1`.
- **Model 1_1 calibration present**: `../model1_1/calibration/k_table.json`
  (build once with `python ../model1_1/calibration/calibrate.py`).
- The `../common` kernel image pushed (`pippina2/model1-kernel:v0.1.0`).
- `kubectl` context pointing at the rt-cluster.

## Run it

**1. Apply node-prep + sampler DaemonSets** (once):

```bash
node-prep/apply.sh                  # DETECT-ONLY cpu-map.json (per-core sibling table; offlines NOTHING on Azure)
../common/sampler/apply.sh model3   # shared sampler -> /var/lib/model3/samples
```

**2. Sweep BOTH arms into the SAME time-block** (cells run sequentially, delete+recreate):

```bash
TB=tb-$(date +%Y%m%d-%H%M)
python run_model3.py --arm physical                       --timeblock $TB
python run_model3.py --arm sibling  --sibling-load saturating --timeblock $TB
```

Both arms into one `$TB` is what lets `analyze.py` pair them into the C-inflation
table. Useful flags: `--scales tight`, `--only-u 0.8 0.94`, `--max-cell-seconds N`,
`--dry-run`.

**3. Analyze + plot**:

```bash
python analyze.py        --timeblock $TB     # model3-summary.csv + model3-inflation.csv
python plots/plot_all.py --timeblock $TB
```

Preview the derived grid + reused K/C_baseline without touching the cluster:

```bash
python model3lib.py --arm physical
python model3lib.py --arm sibling --sibling-load saturating
```

## Results layout

```
results/<timeblock>/
  physical/<scale>/U<u>/jobs.csv                 per-job C,R,delay,dispatch,miss (clean core)
  physical/<scale>/U<u>/jobs_with_covariates.csv + steal/IRQ/softirq joined per window
  physical/<scale>/U<u>/cell.json                provenance + placements + derived (tail, supply)
  sibling/<scale>/U<u>/jobs.csv                  per-job (RT core, interferer on HT sibling)
  sibling/<scale>/U<u>/interferer.csv            the interferer's own log (provenance)
  sibling/<scale>/U<u>/cell.json                 + rt_cpu / sibling_cpu / sibling_load
  samples/{cpu,tasks,server}.csv                 continuous covariate streams (incl. sibling cpu)
  model3-summary.csv                             one row per (arm, scale, U)
  model3-inflation.csv                           one row per (scale, U): C_phys, C_sib, inflation, supply
  figures/*.png (+pdf)
```

## Figures

1. `fig_c_ccdf_<scale>_U<u>` — **C distribution physical vs sibling** (the core
   C-inflation figure; `Q` line shows `C` crossing the budget ⇒ miss).
2. `fig_c_inflation_vs_u` — **C-inflation factor vs U, tight & soft overlaid**
   (≈ constant relative inflation across scales ⇒ execution-layer fingerprint).
3. `fig_R_miss_vs_u_<scale>` — R percentiles + deadline-miss rate, physical vs sibling.
4. `fig_provisioning_vs_delivery_<scale>` — **`α_eff` & `Δ_eff` stay intact** in the
   sibling arm while the miss rate rises ("the server got `Q` but the task missed").
5. `fig_dose_response` — C-inflation vs sibling-load `{off..saturating}` at fixed `U`
   (needs `--dose-timeblocks`; see [interferer README](manifests/interferer/README.md)).
6. `fig_covariate_scatter` — delay-layer attribution `R−C` vs `steal+IRQ`.

## Hard-won caveats baked in (shared with Model 1_1 / 2)

- **Never offline a vCPU on D4s_v5** — it wedges the VM and zeroes the RT budget
  chain. `node-prep` is **detect-only**; `offline-sibling.sh` is **guarded**
  (needs `FORCE=1`, which you must NOT use on Azure). On Azure the **physical arm**
  achieves its clean core by leaving the RT core's sibling **idle** (no interferer),
  and the reused `C_baseline` is the isolated-core reference. True HW offlining
  (non-Azure) makes the physical arm a hard-isolated core.
- The rt-DRA driver is **SMT-blind** and worst-fit; Model 3 does **not** fight it —
  it reads the RT container's actual `RT_CPUSET` and pins the interferer onto that
  CPU's HT sibling itself, guaranteeing co-location and recording both CPUs.
- **`U ≥ 0.95` is unschedulable** (driver admits only `reqUtil < 950‰`); the grid
  tops out at `U=0.94`.
- **Read counters via the sampler pod**, never `kubectl exec` into a FIFO-90 cell.
- **Divergent high-load tails are unbounded** — reported as *diverges*, not fixed;
  use `--max-cell-seconds` for controlled boundary runs.

## Confirmed inputs (the prompt's two questions)

Both were already **confirmed in Model 1_1 / Model 2** and are reused here (recorded
in [config.yaml](config.yaml)). If Model 3 must differ, change them in `config.yaml`
and re-run `render.py --all`:

1. **KubeDeadline reservation API** — rt-DRA `RtClaimParameters`
   (`rt.resource.example.com/v1alpha1`): `runtime→Q`, `period→P`, `count→m`, in
   microseconds; resource class `rt.example.com`; admission `reqUtil < 950‰`.
   **Confirmed** against the known-good baseline
   [`workloads/rt-dra-verify/rt-verify.yaml`](../../../workloads/rt-dra-verify/rt-verify.yaml)
   (`RtClaimParameters {count,runtime,period}` + `ResourceClaimTemplate` →
   `resourceClassName: rt.example.com` + `parametersRef` → `RtClaimParameters`).
   Model 3 renders per-cell **unique** object names for the sweep; the structure is
   identical to that single-pod example.
2. **Container image** — reuse `pippina2/model1-kernel:v0.1.0` (same `matmul` probe
   for both the RT task and the interferer).
