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

**4. Hypervisor steal-time instrumentation.** Layers 1-3 only reach guest-OS
behaviour; whether Azure's Hyper-V host itself preempts the vCPU underneath
the guest (steal time) is a separate, guest-invisible-by-default question.
`matmul.c` was instrumented to read `/proc/stat`'s per-cpu `steal` field
(USER_HZ-tick resolution, ~10ms) immediately around each timed job, in
addition to the sub-microsecond `CLOCK_THREAD_CPUTIME_ID`/`CLOCK_MONOTONIC`
timestamps already collected. Checked directly, under confirmed real
sustained load on the correct worker/core: steal was genuinely 0. The
instrumentation's own overhead (measured via a standalone microbenchmark,
1,000,000 calls to the same `/proc/stat`-read path: ~8.2μs/call) is
negligible and structurally outside the `C_cputime` measurement window, so
it doesn't itself corrupt the timing it's meant to audit.

**5. Verification that 1-4 are actually taking effect, not just applied
(2026-09-03/05).** Configuring a boot parameter or writing a sysfs file is
not evidence it's doing anything — two cases where checking the *effect*,
not just the *setting*, mattered:

- **`nohz_full` looked broken, wasn't.** The obvious verification counter
  (`LOC:` in `/proc/interrupts`, the traditional LAPIC local-timer line)
  read 0 on every core, including the non-isolated one — which should tick
  normally and didn't, the tell that `LOC` was the wrong line entirely. This
  kernel runs as a Hyper-V guest and uses Hyper-V's own paravirtualized
  synthetic timer (`HVS:` "Hyper-V stimer0 interrupts"), not a bare-metal
  LAPIC — confirmed via `dmesg`, `systemd-detect-virt`, and
  `/sys/bus/vmbus/devices`. Checked against the right counter (two
  timestamped snapshots 5s apart while a real paced round ran on the
  isolated core), the tick rate first came back at ~1002/sec — a plain
  1000Hz tick, one to two orders of magnitude above what the workload's own
  period needs. Root cause: two leftover diagnostic busy-loop shell
  processes (`sh -c 'while :; do :; done'`), still pinned to the same core
  and still runnable, left over from an earlier steal-time stress test in
  the same working session. `nohz_full`'s tick-suppression precondition —
  *exactly one runnable task on the core at all times* — was being violated
  continuously. Killing them dropped the rate to ~66/sec, a 15x drop,
  confirming `nohz_full` works as intended once genuine single-task
  occupancy holds; the small residual above the workload's own theoretical
  rate wasn't pursued further given how much of the effect this already
  explains. Any round collected while the busy-loops were alive is
  contaminated and was re-collected, not reused.
- **IRQ affinity** — checked directly rather than assumed: at check time, no
  device IRQ's `smp_affinity_list` included the isolated core under test.
  This was a one-off, point-in-time check on one node, not a persistent
  guarantee — `node-prep/steer-irqs.sh` exists to move IRQs off an RT core
  on demand, but it was built for model4's activation-mechanism arms
  specifically and is invoked manually, not wired into every model's
  baseline setup or re-applied automatically after a reboot.

**Checked and already fine, no action taken:** `nmi_watchdog=0` (periodic
lockup-detection NMI already disabled). **Checked, deliberately left as-is
rather than a gap:** SMT is globally on and core 2's sibling (core 3) was
confirmed to carry only idle per-cpu kthreads at check time — but SMT is not
being tuned away as a hygiene measure, because Johan explicitly named
SMT on/off as its own experimental axis (this is exactly what model3's
sibling-vs-physical-pair design already varies), not noise to eliminate.
**Checked, found not observable from the guest at all:** per-C-state idle
entry counters (`cpuidle/state*/usage`) don't exist in this Hyper-V guest's
sysfs — the hypervisor manages real idle-state entry opaquely, outside guest
visibility, so this candidate is moot rather than unaddressed.

**Identified but not applied — real remaining guest-side levers, in
priority order if pursued further:** `transparent_hugepage=never` (currently
`madvise`, a real but small step short of fully disabling background
`khugepaged` scanning); `mitigations=off` (Spectre/Meltdown mitigations
currently on by default, add measurable syscall/context-switch overhead —
legitimate to disable on a controlled research testbed, needs a reboot,
untried); persisting IRQ affinity/steering across reboots via a systemd
unit or `irqbalance`'s `IRQBALANCE_BANNED_CPULIST` rather than the current
manual, one-shot `steer-irqs.sh` invocation; a `cpuset` cgroup partition
(`cpuset.cpus.partition=isolated`) as a belt-and-suspenders accounting
boundary on top of `isolcpus` (largely redundant given `isolcpus` already
removes the core from the scheduler domain, not expected to change results);
`numactl --hardware` was never actually run to confirm this VM SKU is
single-NUMA (likely, for these sizes, but unverified — would make any NUMA
pinning a no-op if true); `hwlatdetect` (checks for SMI activity, which
bypasses the OS entirely) was never run on this cluster; `matmul.c` never
calls `mlockall()`, so a page fault on swapped-out memory could in principle
land on the isolated core mid-measurement — cheap to add, never checked
whether it currently matters.

**Considered and deliberately not pursued:** a `PREEMPT_RT`-patched kernel.
None of the causes confirmed or ruled out this session (guest-scheduler
preemption, hypervisor steal, `nohz_full` misconfiguration) point at
guest-kernel preemption latency as the remaining bottleneck, and the H-CBS
patch already provides admission-controlled RT scheduling semantics
independently of `PREEMPT_RT`. Revisitable if a future finding specifically
implicates guest-kernel non-preemptible sections.

**The hard ceiling — not crossable from inside a standard Azure guest VM.**
Host-level vCPU scheduling (how Hyper-V decides which physical core runs
this VM's vCPU, and when) and System Management Interrupts (which bypass
the OS entirely) are both invisible and uncontrollable from inside the
guest, no matter how completely the guest OS is tuned. This is the layer
Claim 0's own residual noise floor (the ~cv 0.02-0.04 in point 3 above, and
whatever remains after points 4-5) is implicitly measuring by exclusion: it
persists after every guest-side cause that could be checked was checked.
The one real escape from this ceiling is not a guest-side tunable at all —
it is a different Azure product (Dedicated Host / Isolated VM sizes, which
grant a whole physical host and eliminate noisy-neighbour risk at the
hypervisor level). That is an infrastructure decision out of scope for this
phase, not a configuration gap.

The practical implication for reading results: any degradation attributed
to a model/arm in the claims above is degradation *on top of* this baseline
hygiene, not degradation that a naive, un-pinned, un-isolated deployment
would show from noise alone — which is exactly why model1's solo baseline
(Claim 0) still matters even with all measures above in place: it's the
floor that remains *after* hygiene and verification, not before it, and
that floor is now attributable, by elimination, to the hard ceiling above
rather than to anything still fixable from inside the guest.

## Co-runner intensity and persistence (model2's neighbour, model3's competitor)

**Why 40% utilization**: model2's neighbour and model3's competitor share
one fixed reference intensity (`u=0.4`), chosen to be high enough to cause a
*relevant*, clearly-detectable amount of contention rather than a marginal
one. This matters differently for the two pairing mechanisms this thesis
tests: sibling-sharing is a direct hardware effect (two threads contending
for the same physical core's execution ports/caches every cycle both are
scheduled), so even a modest reserved co-runner can matter — `model3_smoke`
(collected at the earlier `u=0.3`) already showed a 52% miss rate at
tight/U0.6, direct evidence that this intensity range is not too weak to
produce a real, even dramatic effect (though some of that specific reading's
severity may be a data-quality artifact rather than clean interference, so
it's suggestive rather than proof). Physical-core separation is a much more
indirect mechanism (only shared last-level cache / memory bandwidth, no
shared execution ports), so it's expected to be comparatively insensitive to
competitor intensity — if it turned out to be just as sensitive as the
sibling case, that would itself be a notable finding pointing at something
beyond SMT sharing, not evidence the intensity was chosen wrong.

The intensity is deliberately the same value for model2, and for all four
of model3's arms — not tuned per arm — because comparing across PAIR_TYPE
(the model3 factorial's main comparison) requires holding everything except
the pairing itself constant; a different intensity per arm would confound
PAIR_TYPE with co-runner load and make that comparison uninterpretable.

**The capacity ceiling this creates**: for every sibling arm (model2,
sib_res, sib_cfs), the target and co-runner share one physical core's real
throughput, so combined reserved utilization must stay under a ~0.95
schedulability ceiling. At `u=0.4` that caps the target's own tested
utilization at 0.5 (`0.5 + 0.4 = 0.9`, keeping the same ~0.05 margin used
throughout). This is a real, if unfortunate, trade-off: a more "relevant"
co-runner intensity buys a stronger, more clearly-detectable contention
signal at the cost of a narrower target-utilization range for the sibling
arms specifically. The physical arms (phys_res, phys_cfs) aren't subject to
this ceiling — target and competitor are on different cores entirely — but
currently share the same capped range for implementation simplicity (one
`utilizations` list per config, since PAIR_TYPE is a run_job.sh-time choice,
not a generation-time one); extending just the physical arms to the full
range is a possible follow-up, not yet implemented.

**Why the competitor persists, and what that requires**: since intensity
never varies across the U sweep, model3's competitor/interferer is created
once per scale and left running for every cell in it (`run_job.sh`'s
`place_fixed_competitor`), rather than recreated per cell — see the
model2-sync-fix discussion for why a per-cell competitor design has its own
race problems this avoids. The cost of that choice: the competitor now has
to survive up to the full length of a scale's sweep (potentially ~1-2
hours), not just one cell's few minutes. In practice it has been observed to
exit on its own after a sustained run (~34 minutes) for a reason not yet
pinned down — `matmul.c` itself has no internal timer or resource limit that
would explain a fixed-duration exit, so the cause is most likely external to
the probe process (cgroup/kubelet/scheduler-level). Rather than block on
root-causing that, `run_job.sh` polls the competitor's pod phase throughout
each cell's run and restarts it if it's no longer `Running` — exactly onto
the same cpu it started on for the unreserved arm (which is commanded
directly via taskset), or re-verified back onto the same cpu for the
reserved arm (retried a few times, since the driver's placement isn't
directly controllable) before resuming. A cell where the competitor dies and
can't be brought back onto the required cpu is treated as a failed attempt
and retried, the same as any other placement failure. Model2's neighbour is
NOT subject to this specific issue, since it's still recreated per cell
(each cell capped around 8 minutes at soft scale) — safely under the
~34-minute mark where this has been observed to occur.

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
