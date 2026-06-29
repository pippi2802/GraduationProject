# Finding: RT Bandwidth Is Not Enforced on the Cloud Node (cgroup v2)

**Date:** 2026-06-14
**Node:** `rt-cluster-worker-0` (Azure D4s_v5, Ubuntu 22.04.5, RT kernel 6.16.0-rc4+)
**Driver:** `dra-rt-driver` (rt-DRA), image `pippina2/dra-rt-driver:v0.1.1`
**Status:** Root cause confirmed empirically. Decision on remediation pending.

---

## TL;DR

After fixing the containerd runtime and the CDI spec bug, RT-DRA pods now **start
and run** — but they receive **no real-time CPU bandwidth enforcement**. An
`rtdra` pod is currently equivalent to a `vanilla` pod that has merely been
**pinned to a CPU set**. The reason is a fundamental mismatch:

- The cluster node runs **cgroup v2 (unified)**.
- The rt-DRA driver enforces RT budgets using a **cgroup v1** interface
  (`cpu.rt_runtime_us` / `cpu.rt_multi_runtime_us` under
  `/sys/fs/cgroup/cpu,cpuacct/...`), which **does not exist on cgroup v2**.

This is not just an implementation gap — it is a **substantive thesis result**
for contribution #2 ("when do KubeDeadline's guarantees break in the cloud?").

---

## Evidence

### 1. The node is pure cgroup v2

```console
$ stat -fc %T /sys/fs/cgroup
cgroup2fs
```

`cgroup2fs` = pure unified cgroup v2. (A hybrid v1/v2 layout would report
`tmpfs`.) Consequently the entire cgroup-v1 controller tree
`/sys/fs/cgroup/cpu,cpuacct/` **does not exist**, so every v1-path probe returned
empty:

```console
$ sudo ls -l /sys/fs/cgroup/cpu,cpuacct/cpu.rt_multi_runtime_us   # (no output)
$ sudo cat   /sys/fs/cgroup/cpu,cpuacct/cpu.rt_runtime_us         # (no output)
$ sudo cat   /sys/fs/cgroup/cpu,cpuacct/kubepods.slice/cpu.rt_runtime_us  # (no output)
```

### 2. The running container has no RT bandwidth — only a cpuset pin

`crictl inspect` of the running workload container (`ctr0` in `pod0`):

```jsonc
"cdi.k8s.io/rt.resource.example.com_a9eb8e37-...": "runtime-100.period-1000/CPUSET=1-2",
"cpuPeriod":  "100000",
"cpuQuota":   "0",          // no CFS quota → unthrottled CFS
"cpuShares":  "2",
"cpusetCpus": "1,2",        // the ONLY thing actually applied
"cpusetMems": "",
"systemd_cgroup": true,
// runtime spec:
"cpu_period": 100000,
"cpu_shares": 2
// (no cpu_rt_runtime / cpu_rt_period anywhere)
```

Interpretation:

- The CDI device injected **environment variables** (`RT_RUNTIME_PERIOD`,
  `RT_CPUSET`) and the **cpuset** (`1,2`).
- There is **no** `cpu_rt_runtime_us` / `cpu_rt_period_us` on the container.
- The container is therefore a **plain CFS task pinned to CPUs 1–2**, with no
  guaranteed real-time runtime budget `(Q, P)`.

### 3. The workload relies entirely on the cgroup layer

The synthetic workload (`kdl-synth-benchmark/workload/src/*.c`) sets **no**
scheduling policy of its own — there is no `sched_setscheduler`, `SCHED_DEADLINE`,
`SCHED_FIFO`, `chrt`, or affinity call, and it does not read the injected
`RT_*` env vars. It is a set of plain CFS threads. All real-time behaviour was
expected to come from the cgroup/runc RT layer — which is exactly the layer that
is inactive here.

### 4. The driver's enforcement code is cgroup-v1-only — and disabled

The RT-budget write path is commented out **and** targets cgroup v1:

- `cmd/dra-rt-kubeletplugin/cgroup.go` → `UpdateParentCgroup()` is fully
  commented out, references an undefined `podRuntimes`, and writes to
  `/sys/fs/cgroup/cpu,cpuacct/.../cpu.rt_multi_runtime_us` (a cgroup-v1 +
  RT-fork-kernel construct).
- `cmd/dra-rt-controller/cgroup.go` is **entirely** commented out (126 lines,
  1 active) — the per-pod / per-container cgroup annotation logic is dead.
- The `(Q, P, m)` **allocation and feasibility math** (controller
  `allocations.go`, `rt.go`, `driver.go`) **is active and works** — it correctly
  produces `runtime=7320 / period=12200` etc. in the `NodeAllocationState`.
  Only the final step — **writing the budget into the kernel** — is missing.

So even if `UpdateParentCgroup` were uncommented as-is, it would write to a path
that does not exist on this node and enforce nothing.

---

## Why this happens (background)

- **RT group scheduling** (`cpu.rt_runtime_us`, `cpu.rt_period_us`, and the RT
  fork's `cpu.rt_multi_runtime_us`) is a feature of the **cgroup v1** `cpu`
  controller. It lets you reserve a portion of each period for `SCHED_FIFO`/
  `SCHED_RR` tasks in a cgroup.
- **cgroup v2** intentionally **dropped** the per-cgroup RT bandwidth interface;
  mainline v2 has no equivalent of `cpu.rt_runtime_us`.
- Modern distributions (Ubuntu 22.04+, and the systemd default) boot with
  **cgroup v2 unified** by default. Kubernetes + containerd happily run on v2.
- Therefore a KubeDeadline-style driver whose enforcement is built on cgroup-v1
  RT group scheduling **silently degrades to "cpuset pin + CFS"** on a default
  modern cloud node. The `(Q, P)` reservation is computed and recorded, but never
  applied to the kernel.

---

## Thesis relevance

This directly answers **contribution #2 — when do KubeDeadline's guarantees break
in the cloud?**

> KubeDeadline's RT-bandwidth enforcement depends on **cgroup v1 RT group
> scheduling**. On a stock modern cloud node (Ubuntu 22.04+, cgroup v2 unified),
> that interface is absent, so the reserved budget `(Q, P)` is **computed but not
> enforced**: the container falls back to CFS with only a cpuset pin. The
> admission/feasibility guarantee holds on paper while the runtime guarantee
> silently disappears.

This is a clean, defensible **negative result** about the portability of
RT-cgroup-based deadline scheduling to default cloud environments.

---

## Open questions (need two single-line probes on the worker)

```bash
# (a) Does the RT kernel fork expose ANY rt cgroup interface on v2?
sudo find /sys/fs/cgroup -name 'cpu.rt*' 2>/dev/null

# (b) Confirm cgroup mode / whether a v1 switch is already on the kernel cmdline
cat /proc/cmdline
```

- If (a) finds nothing → cgroup v2 truly has no RT interface here; enforcement is
  impossible without switching to v1 (or a different mechanism).
- If (a) finds something → the RT fork may expose a v2 RT interface and Option 2
  (below) becomes feasible.

---

## Remediation options

| # | Option | What it takes | Outcome / risk |
|---|--------|---------------|----------------|
| 1 | **Switch worker to cgroup v1** | Add `systemd.unified_cgroup_hierarchy=0` (+ `cgroup_enable=cpuset cgroup_memory=1`) to the kernel cmdline (GRUB), reboot. Verify `/sys/fs/cgroup/cpu,cpuacct/cpu.rt_multi_runtime_us` appears. Then re-implement the driver write. | Most faithful to KubeDeadline's design; gives **real** RT enforcement data — *if* the RT fork supports v1 RT cgroups. Requires reboot; must keep kubelet `cgroupDriver=systemd` + containerd v1 cgroup mode consistent. |
| 2 | **Reimplement enforcement for cgroup v2** | Discover whatever RT interface (if any) the RT kernel fork exposes on v2, write new driver code against it. | Unknown feasibility — mainline v2 has no RT bandwidth iface. Highest effort, uncertain payoff. |
| 3 | **Document as the limitation** | Run the benchmark as-is to *show* `rtdra ≈ vanilla` (no enforcement) and present it as the cloud-breakage finding. | Fast, zero risk, directly supports contribution #2. Weaker if presented alone. |

**Suggested path:** do **Option 1** (switch to cgroup v1 → real enforcement
data) *and* keep **Option 3** as the contrast case ("v2 cloud default = no
enforcement; v1 = enforcement"). The paired result — *the same driver enforces
under v1 and silently degrades under v2* — is a stronger thesis statement than
either result on its own.

---

## Current state (for continuity)

- containerd: RT fork `1.7.19-27-g2c5bb9047` on both nodes; crash-loop fixed.
- CDI spec bug: fixed (`pippina2/dra-rt-driver:v0.1.1`); per-claim specs written;
  pods `1/1 Running`.
- RT enforcement: **NOT active** (this document).
- `(Q, P, m)` allocation math: active and correct.
- Benchmark: can run, but `rtdra` and `vanilla` are currently expected to be
  statistically indistinguishable in RT terms until enforcement is enabled.
