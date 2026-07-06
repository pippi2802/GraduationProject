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

## Directory layout

```
model1/
  config.yaml            # SINGLE SOURCE OF TRUTH — all parameters
  model1lib.py           # shared derivations (Q from U/P, N-map, paths, cell grid)
  run_model1.py          # orchestrator: sequential sweep per --timeblock
  manifests/             # DRA + Pod templates (envsubst) + rendered examples
    rt-cell.template.yaml
    canary.template.yaml
    cell_env.py          # emits shell exports from config (keeps render DRY)
    render.sh            # render one cell / the canary to full YAML
    rendered/            # tight-u95.yaml, soft-u40.yaml, canary.yaml (examples)
  rtapp/                 # rt-app JSON generator + reference template
    generate_rtapp.py
    template.json
  node-prep/             # HT-sibling detection + offline (script + DaemonSet)
    prepare-node.sh  restore-node.sh  node-prep-daemonset.yaml  apply.sh
  sampler/               # covariate + cgroup sampler (DaemonSet; no custom image)
    sampler.py  sampler-daemonset.yaml  apply.sh  Dockerfile(optional)
  parse/                 # analysis
    parse_rtapp.py       # rt-app log -> per-job CSV
    convergence.py       # running-p99.9 stopping-rule checker (used by orchestrator)
    supply.py            # alpha_eff / Delta_eff / empirical supply-bound function
    slice_covariates.py  # cut the continuous sampler stream into a cell window
  results/               # results/<timeblock>/<scale-dir>/U<U>/...
```

`<scale-dir>` is **`tens-of-ms`** (tight, P=10 ms) or **`hundreds-of-ms`**
(soft, P=100 ms) — the two timescales live in two directories.

## The KubeDeadline reservation spec (confirmed)

Reservation goes through the **DRA / rt-DRA** flow (same as
`workloads/rt-dra-verify`), configured in **one place**:
[config.yaml](config.yaml) → `kubedeadline_reservation_spec`.

```yaml
RtClaimParameters (rt.resource.example.com/v1alpha1):
  runtime: Q      # microseconds (see units note below)
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
- Run the driver/orchestrator from Linux (or WSL): the `.sh` renderers use
  `bash`, `envsubst` (`gettext`), and `kubectl`. The Python tools are stdlib +
  PyYAML.

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

## Offline analysis

```bash
# effective bandwidth, service delay, empirical supply-bound function (per cell)
python3 parse/supply.py results/<tb>/tens-of-ms/U0.95/server.csv --period-us 10000

# re-parse an rt-app log to a per-job CSV with a custom warm-up
python3 parse/parse_rtapp.py --logdir results/<tb>/tens-of-ms/U0.95 --out jobs.csv

# inspect the convergence state of a collected cell
python3 parse/convergence.py results/<tb>/tens-of-ms/U0.95/jobs.csv
```

`jobs.csv` columns: `job_index, release_us, start_us, finish_us, C_us, R_us,
slack_us, deadline_miss, tardiness_us`.

## Render manifests without the orchestrator

```bash
cd manifests
./render.sh tight 0.95 tb-example        # RT cell -> full YAML on stdout
./render.sh --canary tb-example          # the continuous canary
# examples already rendered under manifests/rendered/
```

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
