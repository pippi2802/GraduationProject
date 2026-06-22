# RT-DRA verification workload

A tiny, dependency-free workload to **observe** whether the behaviour described
in the KubeDeadline paper is actually happening on your node. It does *not*
assert hard real-time guarantees — it makes the scheduler, parameters, and
periodic behaviour visible so you can compare against the paper.

## What it checks

| # | Check | KubeDeadline expectation |
|---|-------|--------------------------|
| 1 | **Parameters** — the `RT_RUNTIME_PERIOD` / `RT_CPUSET` env the driver injects via CDI | claim's `(runtime, period)` reach the container |
| 2 | **cgroup budget** — `cpu.rt_runtime_us`, `cpu.rt_period_us`, `cpu.rt_multi_runtime_us` of the container's own cgroup | RT bandwidth allocated to the pod's cgroup |
| 3 | **Affinity** — `taskset` cpuset | pod pinned to the allocated CPUs |
| 4 | **Scheduler** — can a task run under `SCHED_FIFO`? | RT tasks run under SCHED_FIFO/RR, not CFS |
| 5 | **Behaviour** — wake-up lateness over N periods | low, bounded jitter under RT vs. higher under CFS |

## Why no custom image

The probe is pure `bash` + coreutils + util-linux (`chrt`, `taskset`), all
present in `ubuntu:22.04`. The script is mounted from a ConfigMap, so there is
nothing to build or push and no network access is required.

## Run it

```bash
cd rt-dra-verify
./apply.sh
kubectl -n rt-verify logs rt-verify
```

`apply.sh` rebuilds the ConfigMap from `verify.sh` each time, so editing the
script and re-applying is enough — no image rebuild.

To re-run after a change:

```bash
kubectl -n rt-verify delete pod rt-verify --ignore-not-found
./apply.sh
```

## Reading the result

The log ends with a `SUMMARY` block. The key line is:

```
scheduler available : SCHED_FIFO (RT)  [matches paper]      <- enforcement working
scheduler available : SCHED_OTHER only [RT NOT enforced]    <- budget/SYS_NICE missing
```

- **`SCHED_FIFO (RT)` + non-zero `rt_runtime_us`** → the node behaves as the
  paper describes: the pod's cgroup carries an RT budget and the task runs as a
  real-time task. Compare section [5] jitter against a CFS run.
- **`SCHED_OTHER only`** → RT is not being enforced. Most likely causes:
  - the pod's cgroup `cpu.rt_runtime_us` is `0` (no budget written — the
    driver's `UpdateParentCgroup` / RT-runc leaf write didn't run), or
  - the container lacks `SYS_NICE` (already granted in `rt-verify.yaml`), or
  - the kernel lacks `CONFIG_RT_GROUP_SCHED` (fixed in the new image).

## Tunables (env in `rt-verify.yaml`)

| Env | Default | Meaning |
|-----|---------|---------|
| `RT_PROBE_PERIOD_MS` | 100 | period of the probe loop (ms) |
| `RT_PROBE_ITERS` | 50 | number of periods measured |
| `RT_PROBE_PRIO` | 90 | SCHED_FIFO priority requested |
| `RT_PROBE_KEEPALIVE` | 86400 | seconds to sleep after the report (0 = exit immediately) |

## Proof to send to the authors (two parts)

The in-pod probe shows what the *container* sees. To prove the **driver/kernel
interface mismatch** to the KubeDeadline/HCBS authors you also need the
**node-side** view (the budget chain leaf→root and the fact that the file the
driver writes does not exist). `collect-evidence.sh` gathers that, read-only.

```bash
# 1) in-cluster pod report (container's view)
./apply.sh
kubectl -n rt-verify logs rt-verify  > pod-report.txt

# 2) node-side evidence (run ON THE WORKER, where the pod cgroups live)
#    copy collect-evidence.sh to the worker first, then:
sudo bash collect-evidence.sh                      # auto-detects the RT pod scope
#    add the kernel-source proof if a checkout is present:
HCBS_SRC=/opt/rt-stack/HCBS-patch sudo -E bash collect-evidence.sh
```

`collect-evidence.sh` emits a timestamped `rt-dra-evidence-<node>-<ts>.txt`
containing:

| Proof | Shows |
|-------|-------|
| **A** | `cpu.rt_multi_runtime_us` (the file the driver writes) is **absent** everywhere in `/sys/fs/cgroup` |
| **B** | `cpu.rt_runtime_us` / `cpu.rt_period_us` **do** exist under cgroup2fs (so it is *not* a v1/v2 problem) — they are just `0` |
| **C** | the RT pod's budget chain is **all-zeros leaf→root** while `cpuset.cpus` is correctly **pinned** (allocation works, enforcement doesn't) |
| **D** | the container's tasks run **`SCHED_OTHER` (CFS)**, not `SCHED_FIFO/RR` |
| **E** | the driver source/logs target the **absent** `cpu.rt_multi_runtime_us` |
| **F** | (optional) the kernel branch registers only `rt_runtime_us`/`rt_period_us`, folding "multi" into a per-CPU vector |

Attach both `pod-report.txt` and the `rt-dra-evidence-*.txt` to the email.

## Files

- `verify.sh` — the in-pod probe (single source of truth; tested standalone)
- `rt-verify.yaml` — namespace, `RtClaimParameters`, `ResourceClaimTemplate`, pod
- `apply.sh` — builds the ConfigMap from `verify.sh` and applies everything
- `collect-evidence.sh` — node-side, read-only evidence collector (run on the worker)
