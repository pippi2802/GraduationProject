#!/usr/bin/env bash
# =============================================================================
# rt-budget-reseed.sh - restore the H-CBS RT-cgroup budget chain on the worker.
#
# WHY: on this custom H-CBS (cgroup v2) kernel the RT budget lives in the chain
#   /sys/fs/cgroup -> kubepods.slice -> kubepods-besteffort.slice
# and the kernel enforces, per CPU, Sigma(children rt_runtime) <= parent. A REBOOT
# (or an experiment) zeroes the chain, after which NO RT pod (KubeDeadline / any
# SCHED_FIFO in a reserved container) can start - runc's write to the leaf
# cpu.rt_runtime_us fails with EINVAL, and even the 10% canary fails.
#
# This script re-seeds the chain. Run it after every boot (a systemd unit,
# rt-budget-reseed.service, does this automatically) or by hand for recovery.
#
# Key facts baked in (learned the hard way - see docs / runbook):
#   * cpu.rt_runtime_us WRITE format is per-core PAIRS: "<run> <cpu> <run> <cpu> ..."
#     (READ format is a positional array "R R R R"; writing that array is parsed
#      as (run,cpu=R) -> ERANGE. A bare scalar -> EINVAL.)
#   * cpu.rt_period_us MUST be written BEFORE cpu.rt_runtime_us (else EINVAL).
#   * Seed TOP-DOWN (root -> kubepods -> besteffort); a parent at 0 => child EINVAL.
#   * The global sysctl kernel.sched_rt_runtime_us must be POSITIVE (never -1; -1
#     disables RT group bandwidth so every cgroup write fails and the chain reads 0).
#   * Writing the ROOT cpu.rt_runtime_us returns EBUSY while a SCHED_FIFO/RR task
#     (e.g. the DRM display kthread card1-crtc0) sits in the root cgroup - so we
#     demote those display kthreads first (harmless on a headless node).
# =============================================================================
set -uo pipefail

RUNTIME_US="${RT_RUNTIME_US:-980000}"   # per-core cgroup runtime (<= global < period)
PERIOD_US="${RT_PERIOD_US:-1000000}"    # RT period (100%)
# Global RT runtime MUST be < period: when global == period there is no slack and
# the kernel refuses to (re)configure the root RT bandwidth while the always-present
# FIFO kernel threads (migration/*, watchdogd, ...) are live -> write returns EBUSY.
GLOBAL_US="${RT_GLOBAL_US:-990000}"     # < PERIOD_US, and >= RUNTIME_US
CG=/sys/fs/cgroup
KP="$CG/kubepods.slice"
BE="$KP/kubepods-besteffort.slice"

log() { echo "[rt-reseed] $*"; }
die() { echo "[rt-reseed] ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "must run as root"

# Build the per-core PAIRS string for all ONLINE cpus: "R 0 R 1 R 2 ..."
ncpu="$(nproc)"
pairs=""
for ((c = 0; c < ncpu; c++)); do pairs+="$RUNTIME_US $c "; done
pairs="${pairs% }"

# 1) Demote SCHED_FIFO/RR DRM/display kthreads out of RT *FIRST*, so the global RT
#    bandwidth (step 2) and later the ROOT cgroup can be reconfigured -- they
#    otherwise block the write with EBUSY. Headless node: display timing is
#    irrelevant. ORDER MATTERS: if the sysctl below runs before this, the global
#    write loses to EBUSY on every boot and RT throttling silently stays at -1.
demote_stray_rt() {
  # $1 = awk name filter (regex of comms to EXCLUDE from demotion)
  local exclude="$1" pid
  while read -r pid; do
    [ -n "$pid" ] || continue
    if chrt -o -p 0 "$pid" 2>/dev/null; then
      log "demoted RT task pid=$pid ($(cat "/proc/$pid/comm" 2>/dev/null))"
    fi
  done < <(ps -eLo pid,cls,comm |
    awk -v ex="$exclude" '($2=="FF"||$2=="RR") && $3 !~ ex {print $1}')
}
# Boot case: only the DRM/display kthreads need moving (invert the DRM match by
# excluding everything that is NOT display).
mapfile -t rt_kthreads < <(ps -eLo pid,cls,comm |
  awk '($2=="FF"||$2=="RR") && $3 ~ /crtc|drm|card|vkms|vblank/ {print $1}')
for pid in "${rt_kthreads[@]:-}"; do
  [ -n "$pid" ] || continue
  if chrt -o -p 0 "$pid" 2>/dev/null; then log "demoted RT display kthread pid=$pid"; fi
done

# 2) Global RT bandwidth: runtime STRICTLY BELOW period (never -1, never == period).
#    -1 DISABLES RT group bandwidth -> every cgroup rt_runtime write reads 0 AND
#    FIFO tasks run unthrottled (a probe pins its core and wedges the node). Period
#    first, then retry the runtime write: a stray RT task (e.g. an orphaned SCHED_FIFO
#    probe from a force-deleted pod) also causes EBUSY, so demote non-essential RT
#    tasks between attempts. HARD-FAIL if it still won't hold (fail loud, not silent).
sysctl -w "kernel.sched_rt_period_us=$PERIOD_US" >/dev/null
ESSENTIAL='migration|watchdog|rcu|ksoftirqd|idle_inject|irq/|kworker'
for attempt in 1 2 3 4 5; do
  if sysctl -w "kernel.sched_rt_runtime_us=$GLOBAL_US" >/dev/null 2>&1; then break; fi
  log "global sched_rt write busy (attempt $attempt/5); demoting stray RT tasks and retrying"
  demote_stray_rt "$ESSENTIAL"
  sleep 1
done
cur="$(cat /proc/sys/kernel/sched_rt_runtime_us)"
log "global sched_rt = $cur/$(cat /proc/sys/kernel/sched_rt_period_us)"
{ [ "$cur" != "-1" ] && [ "$cur" -gt 0 ]; } || die \
  "global kernel.sched_rt_runtime_us is still '$cur' (RT throttling DISABLED); RT pods will wedge the node. Find the blocking RT task: ps -eLo pid,cls,rtprio,comm | awk '\$2==\"FF\"||\$2==\"RR\"||\$2==\"DLN\"'"

# 3) Seed each level: PERIOD first, then RUNTIME (pairs), TOP-DOWN.
seed_level() {
  local d="$1"
  [ -d "$d" ] || { log "skip $d (not present yet)"; return 0; }
  [ -e "$d/cpu.rt_period_us" ] || { log "skip $d (no rt files)"; return 0; }
  echo "$PERIOD_US" > "$d/cpu.rt_period_us" 2>/dev/null || true
  if echo "$pairs" > "$d/cpu.rt_runtime_us" 2>/dev/null; then
    log "seeded $d -> $(cat "$d/cpu.rt_runtime_us")"
  else
    log "FAILED to seed $d/cpu.rt_runtime_us (rc=$?)"
    return 1
  fi
}

rc=0
seed_level "$CG"  || rc=1
seed_level "$KP"  || rc=1
seed_level "$BE"  || rc=1

if [ "$rc" -ne 0 ]; then
  die "one or more levels failed to seed - check for a remaining SCHED_FIFO task in the root cgroup (ps -eLo pid,cls,comm | awk '\$2==\"FF\"')"
fi

log "OK: RT-cgroup chain seeded to ${RUNTIME_US}us/core across ${ncpu} cpus"
