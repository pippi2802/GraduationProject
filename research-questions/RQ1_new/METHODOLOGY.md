# RQ1 methodology — what each model/arm is for, and which claim it answers

RQ1 asks where KubeDeadline's (H-CBS) scheduling guarantees break down when
deployed on Azure IaaS. Rather than one undirected sweep, the experiment is
structured as four models (model1–model4, model4 currently parked) answering
five specific claims. This note maps each model — and model3's four arms —
to the claim it exists to support, and states the mechanism each one is
actually testing.

## The five claims (recap)

- **Claim 0** — Azure IaaS has a non-zero intrinsic noise floor even with
  zero explicit contention.
- **Claim 1** — CBS's own admission control does not protect two
  independently-reserved workloads from interfering when they share a
  physical core's SMT threads.
- **Claim 2** — degradation decomposes into two separable factors: whether
  the co-runner shares a physical core (vs. a different one), and whether
  the co-runner is itself admission-controlled (vs. raw CFS).
- **Claim 3** — miss rate alone doesn't characterize *how* a guarantee
  breaks (isolated misses vs. a cascading run).
- **Claim 4** — the collected tail data can be turned into a concrete
  provisioning rule (safe utilization ceiling per confidence level).

## Stability measures — controlling for platform noise

Every claim above depends on being able to attribute a measured deviation to
the condition under test (co-location, SMT sharing, admission-control
status) rather than to noise the platform itself introduces. Three layers
of hygiene were built up, in the order the problems were actually found:

**1. Frequency pinning (DVFS control).** Azure IaaS VMs otherwise let the
CPU scale its frequency dynamically (`ondemand`/`powersave` governors, turbo
boost engaging opportunistically under load). Since the whole calibration
scheme (`calibrate.py`'s K, the matrix size that produces a target compute
time C) assumes a *fixed* clock speed, any frequency drift directly corrupts
C — the same nominal workload takes a different amount of wall-clock time
depending on the instantaneous frequency, independent of anything about
scheduling or contention. The `rq1-agent` DaemonSet pins this at startup on
every node before any experiment runs: sets every cpu's `scaling_governor`
to `performance`, disables turbo/boost (`intel_pstate/no_turbo=1`,
`cpufreq/boost=0`), and where the platform exposes it, pins
`scaling_max_freq` down to `scaling_min_freq` so min=max (a fixed clock, not
just "no boost"). Verified via
`kubectl exec ds/rq1-agent -- cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor`.

**2. CPU core isolation (`isolcpus`/`nohz_full`/`rcu_nocbs`).** Frequency
pinning alone turned out not to be enough — even with a fixed clock, the
general-purpose Linux scheduler still moves timer ticks, RCU callbacks, and
other kernel housekeeping onto whichever cpus are in use, injecting jitter
into the RT core's execution that has nothing to do with the experimental
condition being tested. `node-prep/isolate.sh` addresses this at the boot
level rather than the runtime level: it stages `isolcpus=`/`nohz_full=`/
`rcu_nocbs=` for every logical cpu except one (`keep_cpu`, default cpu0,
left for kubelet/sshd/general housekeeping) into `/etc/default/grub` via
`nsenter` into the host from the already-privileged, already-hostPID
`rq1-agent` pod, then regenerates the grub config. This only takes effect
after a reboot — deliberately not triggered automatically, since it evicts
every pod on the node — and is verified afterward via `isolate.sh <model>
status`, which reads back `/sys/devices/system/cpu/isolated` and
`/proc/cmdline` to confirm the kernel actually picked up the isolated set,
rather than trusting the staged config alone. It's reversible: `restore`
undoes the grub change (again requiring a reboot to take effect), from a
single preserved backup (`grub.rq1.orig`).

**3. An automated calibration-quality gate as the residual safety net.**
Even with both of the above in place, a small intrinsic noise floor remains
— investigated directly (steal time, SMT-sibling load, and
governor/frequency drift were each individually ruled out as the cause) and
found to be roughly cv 0.02–0.04 on short-duration cells (tight-scale, and
soft-scale's own shortest cell), which is not further reducible without
more invasive measures than are in scope here. Rather than chase that floor
to zero, `run_job.sh`'s calibration gate (`CV_THRESHOLD`, default 0.05) is
set just above it: it rejects and flags any cell whose recorded calibration
cv exceeds that threshold, which now reliably catches *genuinely*
mis-calibrated or broken cells without false-flagging the platform's known,
already-investigated residual floor.

The practical implication for reading results: any degradation attributed
to a model/arm in the claims above is degradation *on top of* this baseline
hygiene, not degradation that a naive, un-pinned, un-isolated deployment
would show from noise alone — which is exactly why model1's solo baseline
(Claim 0) still matters even with all three measures in place: it's the
floor that remains *after* hygiene, not before it.

## Model 1 — solo baseline → Claim 0

**Design**: the target runs alone, no co-runner, no shared core. Utilization
U is swept (0.1–0.94) across two time scales (tight: 10 ms period, soft:
100 ms period), each cell run to 5000 measured jobs.

**What it isolates**: with nothing else scheduled against it, any deviation
from a clean guarantee (miss rate > 0, R/D creeping toward 1) can only come
from the platform itself — hypervisor scheduling jitter, steal time, or
other Azure IaaS effects — not from anything this thesis deliberately
introduces. This is the reference distribution every other model's
degradation gets compared against: without it, an effect seen in model2/3
can't be attributed to co-location specifically, since some of it could just
be baseline cloud noise.

## Model 2 — independently-reserved SMT-sibling contention → Claim 1

**Design**: target (count:1 CBS claim) + one reserved neighbour of fixed
utilization, both admission-controlled, forced onto the two SMT threads of
the *same* physical core. The neighbour is placed first and confirmed
running before the target is even created, so contention is present from
the target's very first job — not a race the target could win.

**What it isolates**: the driver's own admission accounting (confirmed from
its source) tracks utilization per *logical* cpu independently, with no
concept of a physical core's shared execution throughput. Model2 tests
whether that gap is real: two claims that each individually pass admission
can still degrade each other once they share a core's actual execution
units. A clean result here would mean CBS's accounting is sufficient despite
being SMT-blind; a broken result — which is what's been observed — means
admission control alone does not guarantee isolation on SMT hardware.

## Model 3 — 2×2 factorial decomposition → Claim 2

**Design**: target (count:1) forced onto a cpu computed relative to a
fixed-intensity competitor, which is created once per scale and stays up for
the whole utilization sweep (its own intensity never changes, so there's no
reason to recreate it per cell). Two independent factors are varied:

|              | competitor unreserved (CFS)     | competitor reserved (CBS) |
|--------------|----------------------------------|----------------------------|
| **sibling**  | Arm A — `sib_cfs`               | Arm B — `sib_res`          |
| **physical** | Arm C — `phys_cfs`               | Arm D — `phys_res`         |

- **PAIR_TYPE** (sibling vs. physical) isolates whether *sharing a physical
  core's execution units* matters at all, independent of what's sharing it.
- **COMPETITOR_TYPE** (reserved vs. unreserved) isolates whether it matters
  *what kind of thing* is sharing that core — an admission-controlled CBS
  task competing for the same physical throughput, vs. an uncontrolled CFS
  task that shouldn't (in theory) hold real-time priority over the target at
  all.

**What each arm answers**:
- **Arm A (sib_cfs)** — does even a *lower-priority, non-real-time* neighbour
  sharing a physical core degrade the target? Isolates the pure SMT/hardware
  contention effect, with scheduling-class differences working *in favour*
  of the target.
- **Arm B (sib_res)** — same physical-core sharing, but now against a peer
  that is itself properly admission-controlled. Compares directly against
  model2 as a second, differently-parameterized confirmation of Claim 1.
- **Arm C (phys_cfs)** — the "should be clean" control: no shared execution
  units, competitor has no scheduling priority. Establishes the floor this
  factorial should return to when neither factor is active.
- **Arm D (phys_res)** — two properly-reserved, properly-admitted workloads
  on *separate* cores. If this arm still shows degradation while the model1
  baseline doesn't, that points at something beyond SMT sharing (e.g.
  memory bandwidth/cache contention across cores, or a driver-level
  interaction) — a genuinely interesting finding if it appears.

Comparing A vs. C and B vs. D isolates the **PAIR_TYPE main effect** (does
core-sharing matter, holding competitor type fixed); comparing A vs. B and
C vs. D isolates the **COMPETITOR_TYPE main effect** (does admission control
of the co-runner matter, holding core-sharing fixed). Any difference between
those two comparisons (e.g. PAIR_TYPE mattering much more when the
competitor is reserved than when it's unreserved) is the **interaction** —
the most mechanistically interesting outcome, since it would mean the two
factors aren't independent contributors but compound each other.

## Cross-cutting: Claim 3 (severity)

Applies uniformly to every model and arm above via `tail_table.csv`:
`miss_count`, `tardiness_max_us`, and `longest_consecutive_miss_run` are
computed per cell regardless of which model produced it. This is not a
separate experiment — it's a different *lens* on the same collected data,
distinguishing (for whichever model/arm shows degradation) whether that
degradation is a scatter of isolated near-misses or a cascading run.

## Cross-cutting: Claim 4 (provisioning rule)

Also applies uniformly, via `provisioning_table.csv`'s per-scale,
per-confidence-level `U_safe` (the highest utilization at which that
percentile of response times still met deadline, interpolated from
`RoverD_p99`/`RoverD_p999` in `summary.csv`). Run side by side across
model1/2/3's arms, this turns Claims 0–2's qualitative comparisons into a
single quantitative table: how much utilization headroom each contention
condition actually costs you, in the units a practitioner would use to
provision a real workload.

## Summary table

| Model / arm         | Co-runner              | Placement                        | Primary claim(s) |
|----------------------|-------------------------|-----------------------------------|-------------------|
| model1               | none                     | n/a                                | Claim 0 (baseline/noise floor) |
| model2               | 1 reserved neighbour     | forced SMT sibling                 | Claim 1 (admission control vs. SMT) |
| model3 — sib_cfs     | unreserved competitor    | forced SMT sibling                 | Claim 2 (PAIR_TYPE main effect, favourable case) |
| model3 — sib_res     | reserved competitor      | forced SMT sibling                 | Claim 2 (PAIR_TYPE main effect) + confirms Claim 1 |
| model3 — phys_cfs    | unreserved competitor    | forced different physical core     | Claim 2 (control / floor) |
| model3 — phys_res    | reserved competitor      | forced different physical core     | Claim 2 (COMPETITOR_TYPE main effect) |
| all of the above     | —                        | —                                   | Claim 3 (severity) + Claim 4 (provisioning), computed identically for every row |
