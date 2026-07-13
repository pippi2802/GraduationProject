#!/usr/bin/env bash
# =============================================================================
# Model 4 node-prep: detect hyper-thread sibling pairs and record, for each
# physical core, its logical-CPU siblings. Model 4 uses the node's TWO physical
# cores: the RT core (carries the reservation, discovered at runtime from the RT
# container's RT_CPUSET) and the OTHER core (the IRQ sink in the `off` arm). The
# emitted cpu-map.json is used by run_model4 to pick the "other core" cpu for a
# given RT cpu, and by irq-control to steer IRQs on/off the RT core.
#
# DETECT-ONLY by default (DRY_RUN=1): offlining a vCPU on Azure D4s_v5 is
# effectively one-way and WEDGES the VM. The prompt's "offline HT siblings" step is
# in offline-siblings.sh, GUARDED (FORCE=1), and MUST NOT be used on Azure.
#
# Idempotent. Env: MAP_OUT (default /host/var/lib/model4/cpu-map.json).
# =============================================================================
set -euo pipefail
SYS=/sys/devices/system/cpu
MAP_OUT="${MAP_OUT:-/host/var/lib/model4/cpu-map.json}"

die() { echo "FATAL: $*" >&2; exit 1; }
log() { echo "[detect-siblings] $*" >&2; }
[[ -d "$SYS" ]] || die "$SYS not present"

expand_list() {   # "0-1,3" -> "0 1 3"
  local out=() p a b i
  IFS=',' read -ra parts <<< "$1"
  for p in "${parts[@]}"; do
    if [[ "$p" == *-* ]]; then a="${p%-*}"; b="${p#*-}"; for ((i=a;i<=b;i++)); do out+=("$i"); done
    else out+=("$p"); fi
  done
  echo "${out[*]}"
}

declare -A SIBLINGS_OF     # core-leader logical cpu -> "cpu cpu ..."
declare -A CORE_OF         # every logical cpu -> its core-leader cpu
online_cpus=()
for d in "$SYS"/cpu[0-9]*; do
  cpu="${d##*/cpu}"
  if [[ -f "$d/online" ]] && [[ "$(cat "$d/online")" == "0" ]]; then continue; fi
  tsl="$d/topology/thread_siblings_list"
  [[ -r "$tsl" ]] || die "cannot read $tsl"
  read -ra sibs <<< "$(expand_list "$(cat "$tsl")")"
  SIBLINGS_OF["${sibs[0]}"]="${sibs[*]}"
  for c in "${sibs[@]}"; do CORE_OF["$c"]="${sibs[0]}"; done
  online_cpus+=("$cpu")
done
[[ ${#online_cpus[@]} -gt 0 ]] || die "no online CPUs with readable topology"

mapfile -t core_keys < <(printf '%s\n' "${!SIBLINGS_OF[@]}" | sort -n)
log "detected ${#core_keys[@]} physical core group(s):"
for k in "${core_keys[@]}"; do log "  core[$k]: siblings = ${SIBLINGS_OF[$k]}"; done
[[ ${#core_keys[@]} -ge 2 ]] || die "need >= 2 physical cores; found ${#core_keys[@]}"

mkdir -p "$(dirname "$MAP_OUT")"
{
  printf '{\n  "node": "%s",\n  "kernel": "%s",\n' "$(hostname)" "$(uname -r)"
  printf '  "physical_cores": %s,\n' "${#core_keys[@]}"
  printf '  "cores": [\n'
  first=1
  for k in "${core_keys[@]}"; do
    [[ $first -eq 1 ]] && first=0 || printf ',\n'
    printf '    { "leader": %s, "siblings": [%s] }' "$k" "$(echo "${SIBLINGS_OF[$k]}" | tr ' ' ',')"
  done
  printf '\n  ],\n'
  # core_of: logical cpu -> core-leader cpu (so run_model4 can pick the OTHER core)
  printf '  "core_of": {'
  firstc=1
  for c in $(printf '%s\n' "${!CORE_OF[@]}" | sort -n); do
    [[ $firstc -eq 1 ]] && firstc=0 || printf ','
    printf ' "%s": %s' "$c" "${CORE_OF[$c]}"
  done
  printf ' }\n}\n'
} > "$MAP_OUT"
log "wrote CPU map -> $MAP_OUT"; cat "$MAP_OUT" >&2
