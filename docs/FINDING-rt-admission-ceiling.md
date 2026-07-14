# FINDING — the RT admission ceiling is set by the SCHED_DEADLINE fair server, not the advertised 0.95

**Date:** 2026-07-14
**Cluster:** `rt-cluster` (Azure `Standard_D4ds_v5`, 4 vCPU / 2 physical cores), 4 workers.
**Kernel:** HCBS `RT_GROUP_SCHED` / `dl_server`, `7.0.0+` (branch `rt-cgroups-multi-260615`).
**Driver:** rt-DRA / KubeDeadline (`dra-rt-driver`).
**Status:** UNDERSTOOD. A design decision is required (see §6).

---

## 1. Summary (one paragraph)

On this kernel a real-time reservation is admitted by the **kernel's SCHED_DEADLINE
admission control**, not only by the rt-DRA driver. The kernel permanently reserves a
slice of DL bandwidth per CPU for a **"fair server"** (`total_bw`, ~0.20) so that
non-real-time work (kubelet, CFS tasks, pod teardown) cannot be starved. Consequently
the **largest single reservation that can be admitted is `bw − total_bw` ≈ 0.75–0.80 of a
core**, *not* the ~0.95 the driver advertises. A reservation of **U = 0.94 is therefore
rejected** on every node in its current state. Earlier experiments reached U = 0.94 only
because RT admission control was **disabled** at the time (`sched_rt_runtime_us = -1`),
which bypasses this check (and removes the non-RT safety reserve).

---

## 2. The admission rule

Per CPU, a new reservation of utilisation `U` is admitted iff:

```
U + total_bw  ≤  dl_bw->bw
```

- `dl_bw->bw` = the DL/RT bandwidth cap, derived from `sched_rt_runtime_us / sched_rt_period_us`.
- `total_bw` = DL bandwidth already committed on that CPU — dominated by the **kernel fair
  server** reserved for CFS/non-RT (plus any admitted RT pods).
- Units are fixed-point, `1 << 20 = 1048576 = 100%`.

So the **maximum admissible single reservation** is `free = dl_bw->bw − total_bw`.

---

## 3. Measured state of the four workers

`sudo grep -iE "dl_bw->bw|total_bw" /sys/kernel/debug/sched/debug` +
`cat /proc/sys/kernel/sched_rt_runtime_us`:

| node | `dl_bw->bw` (cap) | `total_bw` (reserved) | global `sched_rt_runtime_us` | free budget `bw−total_bw` | max admissible U |
| ---- | ----------------- | --------------------- | ---------------------------- | ------------------------- | ---------------- |
| worker-0 | 996147 = **95%** | 209712 = **20%** | 950000 | ≈ **0.75** | **0.75** |
| worker-1 | 996147 = **95%** | 157284 & 52428 = **15% & 5%** (uneven across CPUs) | 950000 | ≈ 0.80–0.90 (per CPU) | inconsistent |
| worker-2 | 1048576 = **100%** | 209712 = **20%** | 1000000 | ≈ **0.80** | **0.80** |
| worker-3 | 1048576 = **100%** | 209712 = **20%** | 1000000 | ≈ **0.80** | **0.80** |

Two problems are visible:
1. **The nodes are not uniform** — two different caps (95% vs 100%) and two different
   seeded ceilings (0.75 vs ~0.80/0.95). This confounds cross-model comparison.
2. **worker-1 is internally inconsistent** — its CPUs carry different `total_bw`
   (15% and 5%), i.e. an uneven or leaked reservation; its results are unreliable until
   rebooted + re-seeded.

---

## 4. Why U = 0.94 is rejected now

`0.94 + 0.20 = 1.14 > 1.00`. Even on a 100%-cap node the fair server holds 0.20, leaving
only **0.80** for a single reservation, and `0.94 > 0.80`. The same holds (more strictly)
on the 95%-cap nodes (ceiling 0.75). **U = 0.94 does not fit on any node while the 0.20
fair-server reserve is present.**

Note the **two admission gates**, which makes the failure look like a runtime bug:
1. The **rt-DRA driver** admits `reqUtil < 0.95`, so it *allocates* the 0.94 claim and the
   pod is scheduled.
2. The **kernel DL admission** then refuses it → runc's reservation write fails with
   `cpu.rt_runtime_us: invalid argument` / `device or resource busy`. The pod pulls its
   image and then crashes at container create.

---

## 5. Why earlier experiments reached U = 0.94

Two non-exclusive explanations, both consistent with "worked before, rejected now":

1. **Admission was disabled (`sched_rt_runtime_us = -1`) — CONFIRMED by the documented
   procedure.** The kernel's admission check `dl_check_tg` is guarded by
   `if (dl_b->bw != -1 …)`, so with `-1` it is **skipped entirely** — any U (incl. 0.94)
   is admitted, and the 0.20 reserve does not apply. This is not a guess: `model1`'s own
   README prescribes it — *"If RT pods stop admitting: `sudo sysctl -w
   kernel.sched_rt_runtime_us=-1` … and re-seed the chain top-down"*
   (`research-questions/RQ1/model1/README.md`). So the earlier U=0.94 runs were taken with
   RT admission **off** (over-commit possible, no CFS reserve — a busy RT task can then
   starve the node, observed as stuck pod teardowns).
2. **The previous kernel (branch `…-260514`) may also not have run the `dl_server` fair
   server**, so `total_bw ≈ 0` and `0.94 < cap` fit. (Secondary; the `-1` procedure above
   is sufficient on its own to explain it.)

> The raw per-run value is recorded in each cell's `cell.json` node facts
> (`run_model1.py` writes `sched_rt_runtime_us`), but those are git-ignored; the committed
> `summary.json` files do not carry it. The README procedure is the authoritative evidence.

> Implication for prior data: the old high-U runs were collected with RT admission **off**
> (`-1`) — over-commit possible, no CFS reserve. The per-container CBS may still have
> throttled each task to its `(Q,P)`, but the *admission condition* differed from a
> properly admission-controlled run — this must be stated explicitly when comparing to any
> new (finite-admission) data.

---

## 6. Consequences and the decision required

The advertised KubeDeadline ceiling (~0.95) is **not achievable on this kernel with the
CFS fair-server reserve enabled.** The **real** ceiling is `bw − total_bw` ≈ **0.75–0.80**.
Our model grids sweep **U up to 0.94**, so a decision is needed:

- **Option A — reach 0.94:** reduce/disable the fair-server reserve (`total_bw → ~0`), e.g.
  by aligning all nodes at `sched_rt_runtime_us = 1000000` and seeding early before the
  server grows. This reproduces the old effective condition but **removes CFS starvation
  protection** (must manage teardown operationally, and note it as an experimental
  condition). It is close to the old `-1` behaviour.
- **Option B — keep protection, cap the grid:** accept the ~0.80 admissible ceiling, and
  **drop U cells above it** (0.9, 0.94) from the model configs. Safer; reports the real
  admissible limit.

Either way, **all four nodes must first be made uniform** (same `sched_rt_runtime_us`,
same seeded value, same `total_bw`) — reboot + early re-seed — or the models are not
comparable, and worker-1's uneven reservation must be cleared.

---

## 7. Arguably a result, not just an obstacle

The finding itself is thesis-relevant: **on a cloud RT_GROUP_SCHED / dl_server kernel the
usable KubeDeadline reservation ceiling is set by the SCHED_DEADLINE fair-server reserve
(~0.80), below the driver's advertised admission limit (~0.95).** Pushing to 0.94 requires
sacrificing the kernel's non-RT protection — a concrete safety/utilisation trade-off worth
reporting.

---

## 8. How to reproduce / verify (read-only)

```bash
# per node: cap, reserve, and global limit
sudo grep -iE "dl_bw->bw|total_bw" /sys/kernel/debug/sched/debug | sort -u
cat /proc/sys/kernel/sched_rt_runtime_us /proc/sys/kernel/sched_rt_period_us

# seeded chain (root -> kubepods -> besteffort)
for d in /sys/fs/cgroup /sys/fs/cgroup/kubepods.slice \
         /sys/fs/cgroup/kubepods.slice/kubepods-besteffort.slice; do
  printf '%s -> ' "$d"; cat "$d/cpu.rt_runtime_us"; done

# what did the OLD runs use? (checks the -1 hypothesis)
grep -r "sched_rt_runtime_us" <old model1 results>/
```
