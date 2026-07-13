#!/usr/bin/env bash
# =============================================================================
# Model 3 node-prep: detect hyper-thread sibling pairs and record, for each
# physical core, its logical-CPU siblings. Model 3 needs this map to (a) pin the
# sibling-arm interferer onto the RT core's HT SIBLING logical CPU, and (b) verify
# the physical-arm RT core's sibling is idle (or offlined on non-Azure hw).
#
# DETECT-ONLY by default (DRY_RUN=1): offlining a vCPU on Azure D4s_v5 is
# effectively one-way and WEDGES the VM (and zeroes the RT cgroup budget chain).
# The physical arm on Azure therefore just leaves the RT core's sibling IDLE (no
# interferer scheduled there) -> the clean C_baseline case.
#
# On hardware where vCPU hotplug is REVERSIBLE you may, for the PHYSICAL arm ONLY,
# run offline-sibling.sh with FORCE=1 to actually offline the RT core's sibling.
# On Azure DO NOT do this.
#
# Idempotent: re-running always rewrites the map and never changes CPU state here.
# Env: MAP_OUT (default /host/var/lib/model3/cpu-map.json).
# =============================================================================
set -euo pipefail
SYS=/sys/devices/system/cpu
MAP_OUT="${MAP_OUT:-/host/var/lib/model3/cpu-map.json}"

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
declare -A SIBLING_CPU     # every logical cpu -> its (single) HT sibling cpu ('' if none)
online_cpus=()
for d in "$SYS"/cpu[0-9]*; do
  cpu="${d##*/cpu}"
  if [[ -f "$d/online" ]] && [[ "$(cat "$d/online")" == "0" ]]; then continue; fi
  tsl="$d/topology/thread_siblings_list"
  [[ -r "$tsl" ]] || die "cannot read $tsl"
  read -ra sibs <<< "$(expand_list "$(cat "$tsl")")"
  SIBLINGS_OF["${sibs[0]}"]="${sibs[*]}"
  # record each cpu's HT sibling (the OTHER logical in the pair, if any)
  for c in "${sibs[@]}"; do
    other=""
    for o in "${sibs[@]}"; do [[ "$o" != "$c" ]] && other="$o"; done
    SIBLING_CPU["$c"]="$other"
  done
  online_cpus+=("$cpu")
done
[[ ${#online_cpus[@]} -gt 0 ]] || die "no online CPUs with readable topology"

mapfile -t core_keys < <(printf '%s\n' "${!SIBLINGS_OF[@]}" | sort -n)
log "detected ${#core_keys[@]} physical core group(s):"
for k in "${core_keys[@]}"; do log "  core[$k]: siblings = ${SIBLINGS_OF[$k]}"; done

# emit map: per-core siblings + a flat cpu->sibling table the harness uses to pin
# the interferer onto whatever logical cpu the SMT-blind driver placed the RT task.
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
  printf '  "sibling_of": {'
  firstc=1
  for c in $(printf '%s\n' "${!SIBLING_CPU[@]}" | sort -n); do
    [[ $firstc -eq 1 ]] && firstc=0 || printf ','
    if [[ -n "${SIBLING_CPU[$c]}" ]]; then printf ' "%s": %s' "$c" "${SIBLING_CPU[$c]}"
    else printf ' "%s": null' "$c"; fi
  done
  printf ' }\n}\n'
} > "$MAP_OUT"
log "wrote CPU map -> $MAP_OUT"; cat "$MAP_OUT" >&2
