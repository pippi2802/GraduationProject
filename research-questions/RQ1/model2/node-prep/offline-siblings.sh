#!/usr/bin/env bash
# =============================================================================
# Model 2 node-prep: detect hyper-thread sibling pairs and pick ONE logical CPU
# per physical core, recording the mapping. This is the prompt's
# "offline HT siblings so only the 2 physical cores are used" step, BUT it is
# DETECT-ONLY by default (DRY_RUN=1) because offlining a vCPU on Azure D4s_v5 is
# effectively one-way and WEDGES the VM (and zeroes the RT cgroup budget chain).
#
# On hardware where vCPU hotplug is REVERSIBLE, run with FORCE=1 (DRY_RUN=0) to
# actually offline the siblings so only the 2 physical cores remain -> guaranteed
# single-core co-location for Variant 2b. On Azure DO NOT do this; Model 2 instead
# audits each reservation's RT_CPUSET to verify co-location offline.
#
# Idempotent: re-running never double-offlines and always rewrites the map.
# Env: CORE_A_LOGICAL, CORE_B_LOGICAL, MAP_OUT, DRY_RUN (default 1), FORCE.
# =============================================================================
set -euo pipefail
SYS=/sys/devices/system/cpu
MAP_OUT="${MAP_OUT:-/var/lib/model2/cpu-map.json}"
DRY_RUN="${DRY_RUN:-1}"
[[ "${FORCE:-0}" == "1" ]] && DRY_RUN=0

die() { echo "FATAL: $*" >&2; exit 1; }
log() { echo "[offline-siblings] $*" >&2; }
[[ -d "$SYS" ]] || die "$SYS not present"

declare -A SIBLINGS_OF
online_cpus=()
for d in "$SYS"/cpu[0-9]*; do
  cpu="${d##*/cpu}"
  if [[ -f "$d/online" ]] && [[ "$(cat "$d/online")" == "0" ]]; then continue; fi
  tsl="$d/topology/thread_siblings_list"
  [[ -r "$tsl" ]] || die "cannot read $tsl"
  raw="$(cat "$tsl")"
  sibs=(); IFS=',' read -ra parts <<< "$raw"
  for p in "${parts[@]}"; do
    if [[ "$p" == *-* ]]; then a="${p%-*}"; b="${p#*-}"; for ((i=a;i<=b;i++)); do sibs+=("$i"); done
    else sibs+=("$p"); fi
  done
  SIBLINGS_OF["${sibs[0]}"]="${sibs[*]}"
  online_cpus+=("$cpu")
done
[[ ${#online_cpus[@]} -gt 0 ]] || die "no online CPUs with readable topology"

mapfile -t core_keys < <(printf '%s\n' "${!SIBLINGS_OF[@]}" | sort -n)
log "detected ${#core_keys[@]} physical core group(s):"
for k in "${core_keys[@]}"; do log "  core[$k]: siblings = ${SIBLINGS_OF[$k]}"; done
[[ ${#core_keys[@]} -ge 2 ]] || die "need >= 2 physical cores; found ${#core_keys[@]}"

read -ra sibs_a <<< "${SIBLINGS_OF[${core_keys[0]}]}"
read -ra sibs_b <<< "${SIBLINGS_OF[${core_keys[1]}]}"
core_a="${CORE_A_LOGICAL:-${sibs_a[0]}}"
core_b="${CORE_B_LOGICAL:-${sibs_b[0]}}"

offline=()
for c in "${sibs_a[@]}"; do [[ "$c" != "$core_a" ]] && offline+=("$c"); done
for c in "${sibs_b[@]}"; do [[ "$c" != "$core_b" ]] && offline+=("$c"); done
log "core A -> cpu$core_a ; core B -> cpu$core_b"
log "sibling(s) that WOULD be offlined -> ${offline[*]:-<none>}"

if [[ "$DRY_RUN" != "1" ]]; then
  log "FORCE offline requested (NOT Azure-safe)."
  for c in "${offline[@]}"; do
    f="$SYS/cpu$c/online"
    [[ -w "$f" ]] || die "cannot write $f (need privileged)"
    [[ "$(cat "$f")" == "0" ]] && log "cpu$c already offline" || { echo 0 > "$f"; log "cpu$c set offline"; }
  done
else
  log "DRY_RUN=1: detect-only, not modifying CPU online state (Azure-safe)."
fi

mkdir -p "$(dirname "$MAP_OUT")"
{
  printf '{\n  "node": "%s",\n  "kernel": "%s",\n' "$(hostname)" "$(uname -r)"
  printf '  "core_a_cpu": %s,\n  "core_b_cpu": %s,\n' "$core_a" "$core_b"
  printf '  "core_a_siblings": "%s",\n  "core_b_siblings": "%s",\n' "${sibs_a[*]}" "${sibs_b[*]}"
  if [[ "$DRY_RUN" == "1" ]]; then printf '  "offline_siblings": [],\n'
  else printf '  "offline_siblings": [%s],\n' "$(IFS=,; echo "${offline[*]:-}")"; fi
  printf '  "physical_cores": %s,\n  "dry_run": %s\n}\n' "${#core_keys[@]}" "$DRY_RUN"
} > "$MAP_OUT"
log "wrote CPU map -> $MAP_OUT"; cat "$MAP_OUT" >&2
