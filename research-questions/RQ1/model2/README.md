# Model 2 — Co-located-contention RT experiment (KubeDeadline / RQ1)

Does a KubeDeadline reservation **firewall** a target real-time container from
**co-located demand**? Model 2 answers this with the *same* deterministic
matrix-multiply probe and *same* two-clock delay decomposition as
[`../model1_1`](../model1_1), adding **two contention variants** that isolate the
two levels of the CBS hierarchy.

> **VARIANCE IS THE MEASUREMENT.** The probe (fixed `M×M` double matmul, fixed
> data, `K` reps/job) has near-zero intrinsic variance, so any `R` inflation under
> co-location is the isolation firewall (or its leak) writing its signature. The
> two clocks partition it: `C = CLOCK_THREAD_CPUTIME_ID` (execution layer),
> `R − C` (delay layer: dispatch / preemption / steal).

## The two variants

| variant | flag | what contends | level stressed | measured quantity |
| ------- | ---- | ------------- | -------------- | ----------------- |
| **2a intra** | `--variant intra` | `k` SCHED_FIFO tasks inside **one** reservation share **one** budget `Q` | **inner** (task-vs-task) | per-task `R` spread + `Δ_eff` as `k` grows (server keeps `Q`) |
| **2b inter** | `--variant inter` | `1 + n` **separate** reservations co-scheduled on the same core(s) | **outer** (server-vs-server) | target `α_eff = Q/P` vs neighbour load (flat = firewall holds) |

- **2a** sweeps `k ∈ {1,2,4,8}` at each container `U` (`k=1` = the Model-1
  reference), with **equal** and **victim/greedy** splits of `U` across tasks.
- **2b** has two arms — **target-fixed** (`U=0.4`, sweep neighbour load) and
  **neighbour-fixed** (fixed load, sweep target `U`) — plus a labelled
  **over-subscribe** arm that pushes past the admission limit.

Everything is driven by [config.yaml](config.yaml) — the single source of truth.

## Calibration is REUSED (no recalibration)

Per the experiment directive, Model 2 **does not recalibrate**. It reuses Model
1_1's [`k_table.json`](../model1_1/calibration/k_table.json): because per-job
compute `C` is **linear in `K`**, [model2lib.py](model2lib.py) derives the reps for
any per-task / per-container target compute by scaling that table
(`K = round(C_target / slope)`) — no recalibration.

The **shared kernel image** (`pippina2/model1-kernel:v0.1.0`) is used too — Model 2
just runs *more instances* of the same `matmul` binary from
[`../common/kernel`](../common/kernel).

> **Shared code lives in [`../common`](../common):** the workload (`common/kernel`),
> the sampler (`common/sampler`) and the metrics-analysis library
> (`common/rtmetrics`: `metrics`, `covariates`, `plotting`). Model 2's `analyze.py`
> and `plots/plot_all.py` import those primitives; only the config, manifests,
> orchestrator and the intra/inter figure set are model-specific.

## Layout

```
config.yaml            all parameters (DRY): scales, U grid, variant grids, reused calibration/image
model2lib.py           shared derivations (Q, reused-K scaling, cell grids, names, paths)
manifests/
  template/            intra-cell + inter-reservation templates + render.py
  intra/{tight,soft}/  committed rendered intra cells (render.py --all)
  inter/{tight,soft}/  committed rendered inter cells (per arm)
node-prep/             offline-siblings.sh (DETECT-ONLY, guarded) + online-siblings.sh + DaemonSet
parse/                 join_covariates.py — thin CLI over common/rtmetrics/covariates
run_model2.py          orchestrator: --variant {intra,inter}, sequential sweep, collect
analyze.py             offline reduction (uses common/rtmetrics): {intra,inter}-summary.csv
plots/                 plot_all.py -> figures/ (PNG+PDF), uses common/rtmetrics.plotting
results/               git-ignored
```

## Prerequisites

- A node labelled `experiment-model=model2`
  (`kubectl label node <n> experiment-model=model2`).
- The rt-DRA driver installed (`*.example.com` API), as in `../model1`.
- **Model 1_1 calibration present**: `../model1_1/calibration/k_table.json`
  (build once with `python ../model1_1/calibration/calibrate.py`).
- Model 1_1's kernel image pushed (`pippina2/model1-kernel:v0.1.0`).
- `kubectl` context pointing at the rt-cluster.

## Run it

**1. Apply node-prep + sampler DaemonSets** (once):

```bash
node-prep/apply.sh                  # DETECT-ONLY cpu-map.json (offlines NOTHING on Azure)
../common/sampler/apply.sh model2   # shared sampler -> /var/lib/model2/samples
```

**2. Sweep a variant for a time-block** (cells run sequentially, delete+recreate):

```bash
python run_model2.py --variant intra --timeblock tb-$(date +%Y%m%d-%H%M)
python run_model2.py --variant inter --timeblock tb-$(date +%Y%m%d-%H%M)
```

Useful flags: `--scales tight`, `--only-cell <cell_id> ...`, `--dry-run`.

**3. Analyze + plot** (per variant):

```bash
python analyze.py       --variant intra --timeblock tb-YYYYMMDD-HHMM
python plots/plot_all.py --variant intra --timeblock tb-YYYYMMDD-HHMM
python analyze.py       --variant inter --timeblock tb-YYYYMMDD-HHMM
python plots/plot_all.py --variant inter --timeblock tb-YYYYMMDD-HHMM
```

Preview the derived grid + reused K without touching the cluster:

```bash
python model2lib.py --variant intra     # per-task task_K derived from Model 1_1
python model2lib.py --variant inter      # target_K / neighbour_K per cell
```

## Results layout

```
results/<timeblock>/
  intra/<scale>/<U-k-split>/task{i}.csv                per-task C,R,delay,dispatch,miss
  intra/<scale>/<U-k-split>/task{i}_with_covariates.csv + steal/IRQ/softirq joined per window
  intra/<scale>/<U-k-split>/cell.json                  provenance + placements + derived
  inter/<scale>/<arm>/<cell-id>/target.csv             measured target reservation
  inter/<scale>/<arm>/<cell-id>/neighbour{i}.csv       neighbour load (provenance)
  inter/<scale>/<arm>/<cell-id>/cell.json              + admission (admitted/colocated)
  samples/{cpu,tasks,server}.csv                       continuous covariate streams
  intra-summary.csv / inter-summary.csv                one row per task / per cell
  figures/*.png (+pdf)
```

## Figures

**intra:** `fig_intra_ccdf_<scale>_U<u>` (per-task R CCDF vs k),
`fig_intra_victim_tail_vs_k`, `fig_intra_delta_alpha_vs_k_<split>`
(Δ_eff grows while α_eff stays ≈ U), `fig_intra_C_vs_R`.

**inter:** `fig_inter_alpha_vs_load_<scale>` (flat = firewall holds; sloping =
leak), `fig_inter_R_vs_load_<scale>`, `fig_inter_cross_scale` (persists at soft ⇒
bandwidth leak; fades ⇒ latency leak), `fig_inter_admission` (over-subscribe arm),
`fig_inter_target_sweep_<scale>` (arm B), `fig_inter_covariate_scatter`.

## Hard-won caveats baked in (shared with Model 1_1)

- **Never offline a vCPU on D4s_v5** — it wedges the VM and zeroes the RT budget
  chain. `node-prep/offline-siblings.sh` is **detect-only** (needs `FORCE=1`, which
  you must NOT use on Azure). Co-location for the inter variant is therefore
  **audited** (each pod's `RT_CPUSET` recorded, `colocated_with_target` counted),
  not forced. The rt-DRA driver is **SMT-blind** and worst-fit — it spreads
  reservations across the 4 logical CPUs, so single-physical-core forcing would
  need `isolcpus` (reboot). This is a documented limitation of the inter arm.
- **`U ≥ 0.95` is unschedulable** (driver admits only `reqUtil < 950‰`); over-
  subscription is expressed by letting aggregate demand reach/exceed `950‰` — the
  excess reservation stays `Pending`, which the harness records as the measurement.
- **Read counters via the sampler pod**, never `kubectl exec` into a FIFO-90 cell.
- **Divergent high-load tails are unbounded** — reported as *diverges*, not fixed.

## Confirmed inputs (the prompt's two questions)

Both were already **confirmed in Model 1_1** and are reused here (recorded in
[config.yaml](config.yaml)):

1. **KubeDeadline reservation API** — rt-DRA `RtClaimParameters`
   (`rt.resource.example.com/v1alpha1`): `runtime→Q`, `period→P`, `count→m`, in
   microseconds; resource class `rt.example.com`. **Admission / over-subscription:**
   a reservation admits onto a logical CPU only when
   `(existing per-mille util) + reqUtil < 950`; over-subscription = submitting
   reservations whose aggregate `reqUtil` reaches/exceeds `950‰` (excess stays
   `Pending`).
2. **Container image** — reuse `pippina2/model1-kernel:v0.1.0` (same `matmul` probe).
