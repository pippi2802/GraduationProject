#!/usr/bin/env bash
# =============================================================================
# Model 1 node-prep: detect hyper-thread sibling pairs, pick ONE logical CPU per
# physical core for (RT-under-test, canary), and take their SIBLINGS OFFLINE so
# nothing runs on the paired logical CPUs (no sibling interference).
#
# KubeDeadline does the actual pinning of the reserved container; this script
# only guarantees the sibling CPUs are idle/offline and records the mapping.
#
# Fails LOUDLY if the topology cannot be determined. Idempotent & re-runnable.
#
# Env overrides (optional):
#   RT_CORE_LOGICAL     force the RT logical CPU (else auto: 1st CPU of core 0)
#   CANARY_CORE_LOGICAL force the canary logical CPU (else auto: 1st CPU of core 1)
#   MAP_OUT             where to write the JSON mapping (default: /var/lib/model1/cpu-map.json)
#   DRY_RUN=1           detect + print only, do not offline anything
# =============================================================================
set -euo pipefail

SYS=/sys/devices/system/cpu
MAP_OUT="${MAP_OUT:-/var/lib/model1/cpu-map.json}"
DRY_RUN="${DRY_RUN:-0}"

die() { echo "FATAL: $*" >&2; exit 1; }
log() { echo "[node-prep] $*" >&2; }

[[ -d "$SYS" ]] || die "$SYS not present — cannot read CPU topology"

# --- Enumerate online logical CPUs and their physical-core sibling groups -----
declare -A CORE_OF          # logical cpu -> canonical core key (min sibling)
declare -A SIBLINGS_OF      # canonical core key -> "cpuA cpuB ..."
online_cpus=()

for d in "$SYS"/cpu[0-9]*; do
  cpu="${d##*/cpu}"
  # skip offline CPUs (no topology dir when offline)
  if [[ -f "$d/online" ]] && [[ "$(cat "$d/online")" == "0" ]]; then
    continue
  fi
  tsl="$d/topology/thread_siblings_list"
  [[ -r "$tsl" ]] || die "cannot read $tsl (topology unavailable for cpu$cpu)"
  raw="$(cat "$tsl")"                     # e.g. "0,2" or "0-1"
  # normalise ranges/lists into a space-separated list of ints
  sibs=()
  IFS=',' read -ra parts <<< "$raw"
  for p in "${parts[@]}"; do
    if [[ "$p" == *-* ]]; then
      a="${p%-*}"; b="${p#*-}"
      for ((i=a; i<=b; i++)); do sibs+=("$i"); done
    else
      sibs+=("$p")
    fi
  done
  key="${sibs[0]}"                        # canonical = smallest sibling id
  CORE_OF["$cpu"]="$key"
  SIBLINGS_OF["$key"]="${sibs[*]}"
  online_cpus+=("$cpu")
done

[[ ${#online_cpus[@]} -gt 0 ]] || die "no online CPUs with readable topology"

# --- Distinct physical cores (sorted by canonical key) ------------------------
mapfile -t core_keys < <(printf '%s\n' "${!SIBLINGS_OF[@]}" | sort -n)
log "detected ${#core_keys[@]} physical core group(s):"
for k in "${core_keys[@]}"; do
  log "  core[$k]: siblings = ${SIBLINGS_OF[$k]}"
done

[[ ${#core_keys[@]} -ge 2 ]] || \
  die "need >= 2 physical cores (RT + canary); found ${#core_keys[@]}"

# --- Choose primary logical CPU per core + its siblings to offline ------------
core_a="${core_keys[0]}"
core_b="${core_keys[1]}"
read -ra sibs_a <<< "${SIBLINGS_OF[$core_a]}"
read -ra sibs_b <<< "${SIBLINGS_OF[$core_b]}"

rt_cpu="${RT_CORE_LOGICAL:-${sibs_a[0]}}"
canary_cpu="${CANARY_CORE_LOGICAL:-${sibs_b[0]}}"

# every sibling that is NOT the chosen primary of core A or B goes offline
offline=()
for c in "${sibs_a[@]}"; do [[ "$c" != "$rt_cpu" ]] && offline+=("$c"); done
for c in "${sibs_b[@]}"; do [[ "$c" != "$canary_cpu" ]] && offline+=("$c"); done

log "RT-under-test  -> cpu$rt_cpu   (physical core $core_a)"
log "canary         -> cpu$canary_cpu   (physical core $core_b)"
log "offline siblings -> ${offline[*]:-<none>}"

# --- Offline the siblings (unless DRY_RUN) ------------------------------------
if [[ "$DRY_RUN" != "1" ]]; then
  for c in "${offline[@]}"; do
    f="$SYS/cpu$c/online"
    [[ -w "$f" ]] || die "cannot write $f (need privileged/root to offline cpu$c)"
    if [[ "$(cat "$f")" == "0" ]]; then
      log "cpu$c already offline"
    else
      echo 0 > "$f"
      log "cpu$c set offline"
    fi
  done
else
  log "DRY_RUN=1: not modifying CPU online state"
fi

# --- Record the mapping -------------------------------------------------------
mkdir -p "$(dirname "$MAP_OUT")"
{
  printf '{\n'
  printf '  "node": "%s",\n' "$(hostname)"
  printf '  "kernel": "%s",\n' "$(uname -r)"
  printf '  "rt_cpu": %s,\n' "$rt_cpu"
  printf '  "canary_cpu": %s,\n' "$canary_cpu"
  printf '  "offline_siblings": [%s],\n' "$(IFS=,; echo "${offline[*]:-}")"
  printf '  "physical_cores": %s,\n' "${#core_keys[@]}"
  printf '  "dry_run": %s\n' "$DRY_RUN"
  printf '}\n'
} > "$MAP_OUT"
log "wrote CPU map -> $MAP_OUT"
cat "$MAP_OUT" >&2
