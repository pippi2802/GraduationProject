#!/usr/bin/env bash
# =============================================================================
# Model 4 — GUARDED HT-sibling offline (NOT Azure-safe). The prompt's "offline HT
# siblings so only the 2 physical cores are used" step. Requires FORCE=1. On Azure
# D4s_v5 DO NOT run this: offlining wedges the VM and zeroes the RT cgroup budget
# chain. On Azure Model 4 instead uses BOTH logical CPUs and steers IRQs by cpu.
# Env: FORCE (must be 1), SYS (default /sys).
# =============================================================================
set -euo pipefail
SYS="${SYS:-/sys}/devices/system/cpu"
log() { echo "[offline-siblings] $*" >&2; }
die() { echo "FATAL: $*" >&2; exit 1; }
[[ "${FORCE:-0}" == "1" ]] || die "refusing to offline without FORCE=1 (NOT Azure-safe)"

expand_list() { local out=() p a b i; IFS=',' read -ra parts <<< "$1"; for p in "${parts[@]}"; do
  if [[ "$p" == *-* ]]; then a="${p%-*}"; b="${p#*-}"; for ((i=a;i<=b;i++)); do out+=("$i"); done
  else out+=("$p"); fi; done; echo "${out[*]}"; }

declare -A SIBLINGS_OF
for d in "$SYS"/cpu[0-9]*; do
  [[ -f "$d/online" && "$(cat "$d/online")" == "0" ]] && continue
  tsl="$d/topology/thread_siblings_list"; [[ -r "$tsl" ]] || continue
  read -ra sibs <<< "$(expand_list "$(cat "$tsl")")"
  SIBLINGS_OF["${sibs[0]}"]="${sibs[*]}"
done
for k in "${!SIBLINGS_OF[@]}"; do
  read -ra sibs <<< "${SIBLINGS_OF[$k]}"
  for c in "${sibs[@]:1}"; do
    f="$SYS/cpu$c/online"; [[ -w "$f" ]] || { log "cannot write $f"; continue; }
    [[ "$(cat "$f")" == "0" ]] && log "cpu$c already offline" || { echo 0 > "$f"; log "cpu$c offline"; }
  done
done
