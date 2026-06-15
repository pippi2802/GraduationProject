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

## Files

- `verify.sh` — the probe (single source of truth; tested standalone)
- `rt-verify.yaml` — namespace, `RtClaimParameters`, `ResourceClaimTemplate`, pod
- `apply.sh` — builds the ConfigMap from `verify.sh` and applies everything
