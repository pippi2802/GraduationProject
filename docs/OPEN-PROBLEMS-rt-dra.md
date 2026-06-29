# Open Problems: making rt-DRA (KubeDeadline) enforce RT on the cloud cluster

**Last updated:** 2026-06-25
**Cluster:** `rt-cluster-worker-0` (Azure D4s_v5, 4 vCPU), Kubernetes 1.28, **pure cgroup v2**
(`cgroup2fs`), HCBS `RT_GROUP_SCHED` kernel.
**Driver deployed:** `pippina2/dra-rt-driver:v0.1.1`. **Staged (not built):** v0.1.2.

This document lists the **open problems** that currently stop an rt-DRA pod from being
scheduled with real-time bandwidth, what is already understood/fixed, and the order in which
the remaining work must be done.

---

## 1. The enforcement chain (where each problem sits)

For an rt-DRA pod to actually run real-time, every link below must hold:

| # | Link | Owner | Status |
|---|------|-------|--------|
| 1 | DRA allocation `(Q,P,cpuset)` written to NAS | controller | ✅ works |
| 2 | Per-claim **CDI spec** written to `/var/run/cdi` | driver (kubeletplugin) | ✅ fixed in v0.1.1 |
| 3 | `RT_*` env + cpuset injected into container | containerd (CDI) | ✅ works |
| 4 | **Parent slices** seeded with RT budget (root → kubepods → QoS → pod) | driver `UpdateParentCgroup` | ⚠️ coded for v0.1.2, **not deployed** |
| 5 | **Container leaf** seeded with `(Q,P)` | RT-runc | ❌ **broken on cgroup v2** |
| 6 | Workload tasks run `SCHED_FIFO`/`RR` inside the budget | workload / probe | ✅ probe does this |

Links 1–3 are green. The real-time budget never lands because of **links 4 and 5**.

---

## 2. Open problems

### P1 — RT-runc does not seed the container leaf on cgroup v2 *(primary blocker)*
The leaf RT write in `nasim-samimi/runc` lives in **`libcontainer/cgroups/fs/cpu.go`**
(`SetRtSched`), which is the **cgroup v1** code path. Our node is **pure cgroup v2**, where runc
uses **`libcontainer/cgroups/fs2/cpu.go`** — and that file writes only `cpu.weight`/`cpu.max`,
**no RT budget at all**.

> Consequence: on cgroup v2, runc **never writes** the container leaf's `cpu.rt_runtime_us`.
> This is exactly why the verify pod reports `cgroup path: 0::/` with
> `cpu.rt_period_us = 0 / cpu.rt_runtime_us = 0`, regardless of the kernel or the driver.

**Fix:** port the RT logic from `fs/cpu.go` `SetRtSched` into `fs2/cpu.go` so the leaf is seeded
on cgroup v2.

### P2 — Leaf write targets a removed file and uses the wrong format/order
Even in the v1 path, `SetRtSched` writes the leaf to **`cpu.rt_multi_runtime_us`**, which the HCBS
authors **removed** on the current kernel branches and **folded into `cpu.rt_runtime_us`**. It also
formats the value as `<cpuset> <runtime>`.

Per the authors (Andriaccio/Abeni), the new `cpu.rt_runtime_us` accepts:
- a **single scalar** (same runtime on all cores), or
- a **per-core list**: `<runtime> <cpuset> <runtime> <cpuset> …` (e.g. `10000 0-2 20000 3,5`).
  ⚠️ **runtime comes first**, and **cores not listed are set to 0** (the old multi file only
  touched the listed cores).

**Fix (in runc):** write `cpu.rt_runtime_us` (not the multi file), with the `<runtime> <cpuset>`
order, listing every core that needs budget.

> **Note (Family-specific):** the `<runtime> <cpuset>` list applies only to **Family B**
> (`Yurand2000 …-multi`). On **Family A** (`lucabe72 hcbs_dl_server`, dl_server-based) the cgroup-v2
> files are the **classic scalar** `cpu.rt_runtime_us` + `cpu.rt_period_us` — exactly what the driver
> already writes — so P2/P6 do not apply there. See **P7**.

### P3 — Write order must be runtime → period → runtime
The kernel admission test enforces `runtime ≤ period` **at all times**. A fresh child slice starts
at `period = 0`, so a runtime-first write can be rejected with `EINVAL`. The robust sequence the
authors recommend is **write runtime, then period, then runtime again** (the first runtime write
may fail; that is expected and ignored).

**Status:** ✅ done in the **driver** (`seedRtCgroup`, v0.1.2). ❌ still needs doing in **RT-runc**.

### P4 — `UpdateParentCgroup` (parent seeding) is not yet deployed
The driver code that seeds the parent slices (root → `kubepods.slice` → QoS slice → pod slice)
is finished for **v0.1.2** but **not built or deployed**. With v0.1.1 running, nothing seeds the
parents, so even a correct leaf write would be rejected (a leaf can only get budget if every
ancestor already has it).

**Fix:** build + deploy v0.1.2 (also requires a `rollout restart` to pick up the new
`/sys/fs/cgroup` host mount in the kubeletplugin manifest).

### P5 — The pod slice may not exist at `NodePrepareResources` time
The kubelet creates the per-pod slice (`kubepods-…-pod<UID>.slice`) around sandbox setup, which
can be **after** the driver's `NodePrepareResources` runs. If the pod slice isn't present yet, the
driver can only seed the stable parents and must defer the pod-slice/leaf seeding.

**Open question:** confirm from plugin logs whether `UpdateParentCgroup` finds the pod slice
(`seeded podslice=…`) or logs `pod slice not present yet`. If the latter is common, we need a
deferred/retry seed or to rely on RT-runc for the pod slice + leaf.

### P6 — Per-core "unspecified = 0" semantics
Because the new interface zeroes every core not listed, a **scalar** write to a slice sets the
budget on **all** cores. That is fine for the generous shared parents, but the **pod slice / leaf**
should list exactly the allocated cores with the per-core format, or we risk either over-reserving
or zeroing cores another pod needs.

**Decision pending:** keep scalar for parents + per-core list for the leaf (RT-runc), or move the
driver's pod-slice seed to the per-core list too.

### P7 — Kernel branch / version — *TWO distinct HCBS families*
There are **two different HCBS lineages**, with **different cgroup-v2 interfaces**. The driver's
leaf/pod-slice write format depends on which one we standardize on.

| | **Family A — Abeni `hcbs_dl_server`** | **Family B — Yurand2000 `…-multi-260615`** |
|---|---|---|
| Repo/branch | `lucabe72/LinuxPatches @ hcbs_dl_server` (Luca Abeni, the original author) | `Yurand2000/HCBS-patch @ rt-cgroups-multi-260615` |
| Base | Linux **6.13-rc4** | 6.16 / newer |
| cgroup v2 | **native** (patch `0007-Tentative-cgroup-v2-support`); v1 removed (`0015`) | yes |
| Interface | **scalar** `cpu.rt_runtime_us` (µs, s64) + `cpu.rt_period_us` (u64) — per-CPU via `tg->dl_se[cpu]` | `cpu.rt_runtime_us` as a **per-core list** `<runtime> <cpuset> …` |
| Backing | mainline **`dl_server`** → each group is a real **SCHED_DEADLINE / CBS** server | multi-runtime variant |
| Hierarchy | depth≤2 limit **removed** (patch `0008`) → allows root→kubepods→QoS→pod→container | n/a |
| Status | v2 marked *"Tentative / to be tested"* | what the Pisa email recommended |
| Hierarchy rule | RT tasks only in **leaf** RT cgroups; a cgroup with RT-children can't hold RT tasks (k8s fits) | same family of rules |

- **Old `6.16.0-rc4+` (`hufs-eselab @ rt-cgroups-250715`)** is too old / has the admission-test
  problem; drop it regardless.
- **Family A matches our current driver code as-is** (`seedRtCgroup` already writes scalar
  `cpu.rt_runtime_us` + `cpu.rt_period_us`), dissolves **P6**, and gives clean CBS semantics — but
  base is older and v2 is "tentative".
- **Family B** is actively maintained by the authors who emailed us, but needs the **per-core list**
  write (re-introduces **P6**) and the multi-file nuance.

**Decision (OPEN):** pick Family A or Family B. This choice sets the driver's pod-slice/leaf write
format (scalar vs per-core list) and which kernel the worker is re-imaged to.

### P8 — CDI robustness (mostly fixed, not deployed)
Two CDI issues are fixed in v0.1.2 source but not yet shipped:
- **Spec-version floor** — newer RT-containerd rejects CDI specs `< v0.5.0`; one bad spec aborts the
  whole `/var/run/cdi` refresh. v0.1.2 floors written specs to `0.6.0`.
- **Prepare race** — the per-claim spec could be built from a stale NAS cache. v0.1.2 refreshes NAS
  before writing and honors the error ("Solution 1").

### P9 — Re-image fragility (operational)
A worker re-image wipes state that rt-DRA depends on:
- `/var/run/cdi` is **tmpfs** (CDI specs gone on reboot).
- `enable_cdi=true` in `containerd/config.toml` must be re-applied.
- The `ResourceClass rt.example.com` must be recreated (not yet in the Helm chart).
- Calico/CNI state is wiped (separate reinstall).

---

## 3. What already works (do not re-debug)

- DRA allocation math `(Q, P, m)` and NAS state.
- Per-claim CDI spec writing (v0.1.1) → pods reach `1/1 Running`.
- `RT_*` env injection + cpuset pinning.
- The full chain was **manually proven** once: after hand-seeding root → kubepods → QoS → pod →
  leaf (period+runtime at every level), `chrt -f -p 90` returned `SCHED_FIFO`. So **no kernel
  rebuild is required** — the gap is purely the **distribution layer** (P1, P4, P5).

---

## 4. Required fixes, in dependency order

1. **Build + deploy driver v0.1.2** (parent seeding `UpdateParentCgroup` + runtime→period→runtime
   + CDI version floor + prepare-race fix + `/sys/fs/cgroup` mount). *(P3 ✅, P4, P8)*
2. **Patch RT-runc** to seed the **container leaf on cgroup v2**: port RT logic into `fs2/cpu.go`,
   write `cpu.rt_runtime_us` with `<runtime> <cpuset>` order, runtime→period→runtime, add logging.
   *(P1, P2, P3)*
3. **Standardize the kernel** on `rt-cgroups-multi-260615`. *(P7)*
4. **Re-run `rt-dra-verify`** and confirm: `[2]` non-zero `rt_period_us`/`rt_runtime_us`, `[4]`
   `SCHED_FIFO`, `[6]` throttling test runs (CBS/SCHED_DEADLINE enforcing).
5. **Resolve P5/P6** empirically from plugin logs (pod-slice timing; scalar vs per-core leaf).
6. **Harden re-image** (P9): persist `enable_cdi`, add `ResourceClass` to the Helm chart.

---

## 5. One-paragraph summary

rt-DRA already places pods correctly (allocation, CDI env, cpuset) but applies **no RT bandwidth**
because the budget never reaches the cgroup tree. Two distribution gaps remain: the **driver** must
seed the parent slices (coded in v0.1.2, **not deployed**), and **RT-runc** must seed the
**container leaf**, which it currently **does not do on cgroup v2** (its RT code is in the unused v1
path) and which still targets the **removed `cpu.rt_multi_runtime_us`** file. Once both write
`cpu.rt_runtime_us` (per-core, runtime→period→runtime) on kernel `rt-cgroups-multi-260615`, the
manually-proven chain (`chrt → SCHED_FIFO`) should hold automatically.
