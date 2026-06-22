#!/usr/bin/env bash
#
# RT-DRA node-side evidence collector
# -----------------------------------
# Read-only. Run this ON THE WORKER NODE (where the rt-DRA kubeletplugin and the
# pod cgroups live) to produce a single, self-contained report proving the
# driver/kernel interface mismatch:
#
#   PROOF A  The file the driver writes (cpu.rt_multi_runtime_us) exists NOWHERE
#            in the live cgroup tree.
#   PROOF B  The kernel DOES expose cpu.rt_runtime_us / cpu.rt_period_us (so this
#            is NOT a "v2 has no RT interface" problem) -- they are just 0.
#   PROOF C  For the RT pod, the budget chain is all-zeros leaf->root, while the
#            cpuset IS correctly pinned (allocation works, enforcement doesn't).
#   PROOF D  The container's tasks run SCHED_OTHER (CFS), not SCHED_FIFO/RR.
#   PROOF E  The driver source/logs target the absent cpu.rt_multi_runtime_us.
#   PROOF F  (optional) The kernel branch only registers rt_runtime_us/rt_period_us
#            and folds "multi" into rt_runtime_us (per-CPU vector).
#
# Nothing here writes to the system. Output goes to stdout and to a timestamped
# file you can attach to the email.
#
# Usage (on the worker):
#   sudo bash collect-evidence.sh                 # auto-detect RT pod scope(s)
#   sudo bash collect-evidence.sh <leaf-cgroup>   # pin a specific leaf .scope
#   HCBS_SRC=/opt/rt-stack/HCBS-patch sudo -E bash collect-evidence.sh   # add PROOF F
#
# Env:
#   CG            cgroup mount (default /sys/fs/cgroup)
#   HCBS_SRC      path to a checked-out HCBS-patch tree (enables PROOF F)
#   DRIVER_NS     namespace of the dra-rt-driver (default dra-rt-driver) -- only
#                 used if kubectl is available on this host (usually it is not)

set -u

CG="${CG:-/sys/fs/cgroup}"
HCBS_SRC="${HCBS_SRC:-}"
DRIVER_NS="${DRIVER_NS:-dra-rt-driver}"
MULTI_FILE="cpu.rt_multi_runtime_us"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="rt-dra-evidence-$(uname -n)-${TS}.txt"

# Emit to stdout AND the report file.
exec > >(tee "$OUT") 2>&1

hr()  { printf -- '============================================================\n'; }
sub() { printf -- '------------------------------------------------------------\n'; }
log() { printf '%s\n' "$*"; }

read1() { # read a single cgroup file, print "(absent)" if missing
  local f="$1"
  if [ -r "$f" ]; then tr '\n' ' ' < "$f"; echo; else echo "(absent)"; fi
}

policy_name() {
  case "${1:-}" in
    0) echo "SCHED_OTHER (CFS)";; 1) echo "SCHED_FIFO (RT)";; 2) echo "SCHED_RR (RT)";;
    3) echo "SCHED_BATCH";; 5) echo "SCHED_IDLE";; 6) echo "SCHED_DEADLINE";;
    *) echo "UNKNOWN(${1:-?})";;
  esac
}

hr
log "RT-DRA NODE-SIDE EVIDENCE"
log "generated : $(date -Is)"
log "node      : $(uname -n)"
log "kernel -r : $(uname -r)"
log "kernel -v : $(uname -v)"
log "cgroup fs : $(stat -fc %T "$CG" 2>/dev/null) (cgroup2fs => unified v2)"
# RT_GROUP_SCHED from running config if available
if [ -r /proc/config.gz ]; then
  log "RT_GROUP_SCHED : $(zcat /proc/config.gz 2>/dev/null | grep -E '^CONFIG_RT_GROUP_SCHED=' || echo '(not set)')"
elif [ -r "/boot/config-$(uname -r)" ]; then
  log "RT_GROUP_SCHED : $(grep -E '^CONFIG_RT_GROUP_SCHED=' "/boot/config-$(uname -r)" || echo '(not set)')"
else
  log "RT_GROUP_SCHED : (kernel config not readable)"
fi
hr

# ---------------------------------------------------------------------------
# PROOF A: the driver's target file does not exist anywhere
# ---------------------------------------------------------------------------
log "[PROOF A] Does the driver's target file '${MULTI_FILE}' exist in ${CG}?"
sub
mapfile -t MULTI_HITS < <(find "$CG" -name "$MULTI_FILE" 2>/dev/null)
if [ "${#MULTI_HITS[@]}" -eq 0 ]; then
  log "  RESULT: 0 occurrences. '${MULTI_FILE}' is ABSENT from the entire cgroup tree."
  log "  => Every write the driver does to this filename has NO target (silently lost)."
else
  log "  RESULT: ${#MULTI_HITS[@]} occurrence(s) found:"
  printf '    %s\n' "${MULTI_HITS[@]}"
fi
hr

# ---------------------------------------------------------------------------
# PROOF B: which RT cgroup files DO exist, and their root values
# ---------------------------------------------------------------------------
log "[PROOF B] Which cpu.rt_* files DOES the kernel expose? (root of ${CG})"
sub
mapfile -t RT_FILES < <(find "$CG" -maxdepth 1 -name 'cpu.rt_*' 2>/dev/null | sort)
if [ "${#RT_FILES[@]}" -eq 0 ]; then
  log "  (no cpu.rt_* files at cgroup root)"
else
  for f in "${RT_FILES[@]}"; do
    log "  $(basename "$f") = $(read1 "$f")"
  done
fi
log "  NOTE: presence of cpu.rt_runtime_us under cgroup2fs proves this kernel"
log "        exposes an RT interface on v2 -- the gap is the MULTI file, not v1/v2."
hr

# ---------------------------------------------------------------------------
# PROOF C: leaf-to-root budget chain for the RT pod(s)
# ---------------------------------------------------------------------------
log "[PROOF C] RT pod budget chain (cpuset pinned, but rt_runtime_us all zero?)"
sub

# Determine the leaf scope(s) to inspect.
LEAVES=()
if [ "${1:-}" != "" ]; then
  LEAVES=("$1")
  log "  using leaf from argument: $1"
else
  # Auto-detect: container scopes under kubepods.slice. Prefer ones whose
  # cpuset.cpus is a strict subset (i.e. pinned by the RT allocation).
  mapfile -t ALL_SCOPES < <(find "$CG" -type d -name '*.scope' -path '*kubepods*' 2>/dev/null | sort)
  if [ "${#ALL_SCOPES[@]}" -eq 0 ]; then
    log "  (no container scopes found under kubepods.slice -- is the RT pod running?)"
  fi
  online="$(cat /sys/devices/system/cpu/online 2>/dev/null || echo '?')"
  for s in "${ALL_SCOPES[@]}"; do
    cs="$(cat "$s/cpuset.cpus" 2>/dev/null || echo '')"
    # Heuristic: pinned (not equal to full online set) AND non-empty.
    if [ -n "$cs" ] && [ "$cs" != "$online" ]; then
      LEAVES+=("$s")
    fi
  done
  if [ "${#LEAVES[@]}" -eq 0 ] && [ "${#ALL_SCOPES[@]}" -gt 0 ]; then
    log "  (no pinned scope detected; dumping ALL container scopes instead)"
    LEAVES=("${ALL_SCOPES[@]}")
  fi
  log "  online CPUs on node: ${online}"
  log "  candidate leaf scope(s): ${#LEAVES[@]}"
fi

dump_chain() {
  local leaf="$1" p
  p="$leaf"
  log "  LEAF: $leaf"
  while :; do
    local label rt rtp cs procs
    label="$(basename "$p")"
    rt="$(read1 "$p/cpu.rt_runtime_us")"
    rtp="$(read1 "$p/cpu.rt_period_us")"
    cs="$(read1 "$p/cpuset.cpus")"
    printf '    %-72s rt_runtime_us=%-12s rt_period_us=%-10s cpuset.cpus=%s\n' \
           "$label" "$rt" "$rtp" "$cs"
    [ "$p" = "$CG" ] && break
    p="$(dirname "$p")"
    case "$p" in "$CG"/*|"$CG") : ;; *) break;; esac
  done
}

for leaf in "${LEAVES[@]}"; do
  [ -d "$leaf" ] || { log "  (skip, not a dir: $leaf)"; continue; }
  dump_chain "$leaf"
  # PROOF D piggybacks here: scheduler policy of the tasks in this leaf.
  log "  [PROOF D] scheduler policy of tasks in this leaf:"
  if [ -r "$leaf/cgroup.procs" ]; then
    while read -r pid; do
      [ -n "$pid" ] || continue
      pol="$(awk '{print $41}' "/proc/$pid/stat" 2>/dev/null)"
      comm="$(tr -d '\0' < "/proc/$pid/comm" 2>/dev/null)"
      log "      pid=$pid comm=${comm:-?} policy=$(policy_name "$pol")"
    done < "$leaf/cgroup.procs"
  else
    log "      (cgroup.procs not readable)"
  fi
  sub
done
hr

# ---------------------------------------------------------------------------
# PROOF E: the driver targets the absent file (source + logs)
# ---------------------------------------------------------------------------
log "[PROOF E] Driver references to '${MULTI_FILE}'"
sub
# (a) source, if a checkout is reachable on this host
DRV_SRC_HITS="$(grep -rn "rt_multi_runtime_us\|writeToParentMultiRuntime\|readCpuRtMultiRuntimeFile" \
                 /root /home /opt 2>/dev/null --include='*.go' | head -20)"
if [ -n "$DRV_SRC_HITS" ]; then
  log "  driver source references (filename the driver writes):"
  printf '    %s\n' "$DRV_SRC_HITS"
else
  log "  (no dra-rt-driver *.go checkout found on this host -- cite cgroup.go from the repo)"
fi
# (b) kubeletplugin logs on this node, if reachable via crictl/containerd
if command -v crictl >/dev/null 2>&1; then
  cid="$(crictl ps -q --name 'kubeletplugin\|dra-rt' 2>/dev/null | head -1)"
  if [ -n "${cid:-}" ]; then
    log "  last kubeletplugin log lines mentioning the multi file / writes:"
    crictl logs "$cid" 2>&1 | grep -iE "rt_multi_runtime|writeToParent|NodePrepareResource|cpu.rt_" | tail -20 | sed 's/^/    /'
  else
    log "  (kubeletplugin container not found via crictl)"
  fi
else
  log "  (crictl not available -- get plugin logs with: kubectl -n ${DRIVER_NS} logs <kubeletplugin-pod>)"
fi
hr

# ---------------------------------------------------------------------------
# PROOF F (optional): kernel source confirms the consolidated interface
# ---------------------------------------------------------------------------
if [ -n "$HCBS_SRC" ] && [ -d "$HCBS_SRC" ]; then
  log "[PROOF F] Kernel source ($HCBS_SRC): registered cpu.rt_* cgroup files"
  sub
  log "  branch: $(git -C "$HCBS_SRC" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  log "  occurrences of '${MULTI_FILE}' in whole tree:"
  n="$(grep -rl "rt_multi_runtime_us" "$HCBS_SRC" 2>/dev/null | wc -l)"
  log "    ${n} file(s)"
  log "  cgroup file .name registrations for rt in kernel/sched/core.c:"
  grep -n '\.name *= *"rt_' "$HCBS_SRC/kernel/sched/core.c" 2>/dev/null | sed 's/^/    /'
  log "  -> if only rt_runtime_us/rt_period_us appear, 'multi' is folded into"
  log "     rt_runtime_us (per-CPU vector) and the separate file was removed."
  hr
fi

log "WRITTEN: ${OUT}"
log "Attach this file to the email. Pair it with the in-cluster pod report:"
log "  ./apply.sh && kubectl -n rt-verify logs rt-verify"
