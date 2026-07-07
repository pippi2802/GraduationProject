# Model 1 — Clean-baseline real-time experiment (KubeDeadline / RQ1)

Runnable experiment harness for the **clean baseline / reference** cell of the
KubeDeadline RQ1 study on AKS.

A single `SCHED_FIFO` task runs **inside** a KubeDeadline `(Q, P, m=1)`
CBS-reserved container, pinned to a genuine **physical core** whose hyper-thread
**sibling is offlined**, with **no co-located workload**. Two purposes:

1. Confirm the reservation holds when "1 vCPU = 1 dedicated core" is *true*.
2. Measure the irreducible **hypervisor steal-time noise floor** (a HOST-level
   effect that shows up even with a single task).

## Two-level hierarchy

| Level | Entity | Parameters | Provides |
|-------|--------|-----------|----------|
| Outer | container = CBS server | `(Q, P, m)` | bandwidth $\alpha = Q/P$, bounded service delay $\Delta = 2(P-Q)$ |
| Inner | one `SCHED_FIFO` task | period = `P`, run = `Q` | consumes the budget |

Model 1 simplification (mandatory): exactly **one** FIFO task, `m = 1`, task
period = `P`, task run = `Q`, so utilization `U = Q/P` coincides for task and
container.

## Parameters (all in [config.yaml](config.yaml) — the single source of truth)

| Scale | Directory | Period `P` | Utilization grid `U` |
|-------|-----------|-----------|----------------------|
| tight | `tight-10ms`  | 10 ms  | 0.2, 0.4, 0.6, 0.8, 0.9, 0.95 |
| soft  | `soft-100ms`  | 100 ms | 0.1, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95 |

`Q` is **derived**: `Q_us = round(U * P_us)` (never hardcoded). Each `(scale, U)`
pair is one experiment **cell**.

## Directory layout

```
model1/
  config.yaml            # SINGLE SOURCE OF TRUTH — all parameters
  model1lib.py           # shared derivations (Q from U/P, N-map, paths, cell grid)
  run_model1.py          # orchestrator: sequential sweep per --timeblock
  manifests/
    namespace.yaml       # the model1 namespace (rendered)
    tight-10ms/          # rendered per-U cells: U0.2.yaml … U0.95.yaml
    soft-100ms/          # rendered per-U cells: U0.1.yaml … U0.95.yaml
    canary.yaml          # long-lived canary on the OTHER physical core (rendered)
    template/            # the single DRY source + generator
      rt-cell.template.yaml   # ${VAR} template for a cell
      canary.template.yaml    # ${VAR} template for the canary
      render.py               # pure-Python renderer (no envsubst); also `--all`
  rtapp/                 # rt-app JSON generator + reference template
    generate_rtapp.py  template.json
  node-prep/             # HT-sibling detection + offline (script + DaemonSet)
    prepare-node.sh  restore-node.sh  node-prep-daemonset.yaml  apply.sh  README.md
  sampler/               # covariate + cgroup sampler (DaemonSet; no custom image)
    sampler.py  sampler-daemonset.yaml  apply.sh  Dockerfile
  parse/                 # analysis primitives
    parse_rtapp.py       # rt-app log -> per-job CSV
    convergence.py       # running-p99.9 stopping-rule checker (used by orchestrator)
    supply.py            # alpha_eff / Delta_eff / empirical supply-bound function
    slice_covariates.py  # cut the continuous sampler stream into a cell window
  plots/                 # one script per figure + shared common.py + plot_all.py
  results/               # results/<timeblock>/<scale-dir>/U<U>/…  (git-ignored)
```

## The KubeDeadline reservation spec (confirmed)

Reservation goes through the **DRA / rt-DRA** flow (same as
`workloads/rt-dra-verify`), configured in **one place**:
[config.yaml](config.yaml) → `kubedeadline_reservation_spec`.

```yaml
RtClaimParameters (rt.resource.example.com/v1alpha1):
  runtime: Q      # microseconds
  period:  P      # microseconds
  count:   m      # cores (= 1 for Model 1)
ResourceClaimTemplate (resource.k8s.io/v1alpha2) -> resourceClassName: rt.example.com
Pod: spec.resourceClaims[].source.resourceClaimTemplateName + container resources.claims[]
```

**Units:** `runtime`/`period` are emitted in **microseconds** (matches cgroup
`cpu.rt_runtime_us`/`cpu.rt_period_us` and keeps `U=0.95` tight → `Q=9500`
integer). If your CRD instead wants **milliseconds**, set
`kubedeadline_reservation_spec.units: milliseconds` in config — the generator
divides by 1000 everywhere. Nothing else changes.

KubeDeadline performs the CPU pinning/affinity for the reserved container — the
Kubernetes **CPU Manager is intentionally not used**.

## Container image (confirmed)

**No custom image.** Pods use `ubuntu:24.04` and `apt-get install rt-app` at
start from a ConfigMap-mounted entrypoint (mirrors `rt-dra-verify`). The sampler
DaemonSet likewise installs `python3` at runtime. See `image:` in config.

## Prerequisites

- An AKS cluster with the **KubeDeadline / rt-DRA driver installed** (provides
  `resourceClassName: rt.example.com` and the `RtClaimParameters` CRD).
- One RT worker node, ideally `Standard_D4s_v5` (4 vCPU / 2 physical cores).
- `kubectl` context pointing at the cluster; on the RT node the kernel should
  allow RT bandwidth (`kernel.sched_rt_runtime_us` ≠ 0, or `-1`). The orchestrator
  records these per cell.
- Python 3.9+ with **PyYAML** (harness + rendering). Analysis/plots additionally
  need **numpy** and **matplotlib**. Rendering and plotting are pure-Python and
  cross-platform (Windows/macOS/Linux); the cluster-facing steps need `kubectl`
  and (for node-prep) a Linux node.

```bash
pip install pyyaml numpy matplotlib
```

## Rendered manifests (already committed, directly applyable)

Every `(scale, U)` cell is pre-rendered so you can apply any single cell by hand:

```bash
kubectl apply -f manifests/namespace.yaml
kubectl apply -f manifests/tight-10ms/U0.95.yaml     # one cell
kubectl apply -f manifests/canary.yaml               # the continuous canary
```

Regenerate all rendered files from the DRY template after any config change:

```bash
python manifests/template/render.py --all
# or render one cell / the canary to stdout:
python manifests/template/render.py --scale tight --u 0.95 --timeblock tb-example
python manifests/template/render.py --canary --timeblock tb-example
```

(The committed files use `--timeblock manual`; the orchestrator renders on the
fly with the real time-block label.)

## Run one time-block

```bash
# 0) label the RT node and (optionally) taint it for exclusivity
kubectl label node <NODE> model1/rt-node=true

# 1) node prep: detect HT siblings + take them offline (privileged DaemonSet)
cd node-prep && ./apply.sh && cd ..
kubectl -n model1 logs ds/model1-node-prep     # verify the CPU map

# 2) start the continuous covariate/cgroup sampler
cd sampler && ./apply.sh && cd ..

# 3) run the full sequential sweep as a labelled time-block
python3 run_model1.py --timeblock tb-$(date +%Y%m%d-%H%M)
```

The orchestrator:
- starts the **canary** (fixed `U=0.1`, its own physical core) and **keeps it up**;
- runs cells **strictly sequentially** (one RT container-under-test at a time),
  **delete+recreate** between cells;
- collects jobs until the **per-cell stopping rule** fires: convergence of the
  running **p99.9** of response time within `[N_min, N_max]`, or the **3 h guard**;
- writes per-cell `rt-app.log`, `jobs.csv`, sliced `server.csv`/`covariates.csv`,
  and `cell.json` metadata under `results/<timeblock>/<scale-dir>/U<U>/`;
- writes `results/<timeblock>/summary.json`.

Useful flags: `--dry-run`, `--scales tight`, `--only-u 0.9 0.95`,
`--skip-canary`, `--results-root <dir>`.

### Stopping rule (from config)

- Warm-up: discard the first **1000** jobs.
- Convergence: p99.9 over all `N` vs. over the first 80% differs by **< 1%**.
- Floors/ceilings: `N_min = 100000` all cells; `N_max = 1e6` for tight
  `U∈{0.9,0.95}` (tail is the story); `N_max = 100000` otherwise.
- Hard guard: **3 h** per cell (recorded if it fires).

## Add more time-blocks

Re-run step 3 with a new label across different hours/days (recommended 3–5×):

```bash
python3 run_model1.py --timeblock tb-20260707-0300
python3 run_model1.py --timeblock tb-20260707-1500
```

Each lands in its own `results/<timeblock>/…`. Aggregate analysis combines jobs
per cell across time-blocks (hypervisor steal is time-correlated → temporal
spread matters as much as raw `N`). The node-prep and sampler DaemonSets stay up
across all time-blocks.

## Figures

All figures are regenerable from `results/` alone. Each script is standalone and
also runnable via the wrapper:

```bash
python plots/plot_all.py --timeblock aggregate     # every figure, all time-blocks
python plots/fig04_cross_scale_overlay.py          # a single figure
```

Figures land in `results/<timeblock or 'aggregate'>/figures/` (PNG + PDF):

| Script | Figure |
|--------|--------|
| `fig01_response_ecdf_ccdf.py` | R CCDF per cell, log tail axis, one panel per scale |
| `fig02_C_vs_R_violin.py`      | execution-time `C` vs response-time `R` violins per U |
| `fig03_tail_vs_util.py`       | p50/p99/p99.9/max of R vs U, per scale |
| `fig04_cross_scale_overlay.py`| **cross-scale** percentile-vs-U overlay (key RQ1 figure) |
| `fig05_supply.py`             | `alpha_eff` & `Delta_eff` vs U with theory lines |
| `fig06_deadline_miss.py`      | miss-rate + tardiness vs U (log y; 3/N bound at 0 miss) |
| `fig07_covariate_scatter.py`  | steal / IRQ vs R-tail (positive attribution) |
| `fig08_timeseries.py`         | R + steal/IRQ + canary vs wall time (coincidence) |
| `fig09_evt_diag.py`           | EVT mean-excess + return-level for tight high-U |
| `fig10_timeblock_compare.py`  | p99.9 per cell across time-blocks |

## Offline analysis primitives

```bash
# effective bandwidth, service delay, empirical supply-bound function (per cell)
python3 parse/supply.py results/<tb>/tight-10ms/U0.95/server.csv --period-us 10000

# re-parse an rt-app log to a per-job CSV with a custom warm-up
python3 parse/parse_rtapp.py --logdir results/<tb>/tight-10ms/U0.95 --out jobs.csv

# inspect the convergence state of a collected cell
python3 parse/convergence.py results/<tb>/tight-10ms/U0.95/jobs.csv
```

`jobs.csv` columns: `job_index, release_us, start_us, finish_us, C_us, R_us,
slack_us, deadline_miss, tardiness_us`.

## Cleanup

```bash
kubectl -n model1 delete pod -l app=model1-rt --ignore-not-found
kubectl -n model1 delete deploy model1-canary --ignore-not-found
kubectl -n model1 delete ds model1-sampler model1-node-prep --ignore-not-found
# bring the offlined hyper-thread siblings back online:
sudo MAP_OUT=/var/lib/model1/cpu-map.json node-prep/restore-node.sh   # (or reboot)
```

## Extending to Models 2/3/4

The harness is deliberately DRY so later models add **config + manifests**, not
rewrites:

- **Model 2 (neighbours):** add co-located workload cells to `config.yaml` and a
  neighbour manifest template; relax the "one container alive" rule in
  `execution:`.
- **Model 3 (HT pinning):** stop offlining the sibling in `node-prep` and pin a
  second task to it; add the sibling CPU to `cpu_assignment`.
- **Model 4 (IRQ steering):** extend `node-prep` to steer IRQs and add the
  affinity to `sampler` covariates.

CPU-only throughout: **no memory/cache stressors** anywhere (Model 1 has no
neighbours regardless).
