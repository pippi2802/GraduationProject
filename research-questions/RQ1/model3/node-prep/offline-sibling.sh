#!/usr/bin/env bash
# =============================================================================
# Model 3 — PHYSICAL-arm offline helper (GUARDED; NOT Azure-safe).
#
# For the physical (reference) arm on hardware where vCPU hotplug is REVERSIBLE,
# offline the RT core's HT sibling so the RT task truly owns the physical core.
# Requires FORCE=1 and the RT core's logical cpu in RT_CPU. Reads the sibling from
# the topology. On Azure D4s_v5 DO NOT run this: offlining wedges the VM and zeroes
# the RT cgroup budget chain. On Azure the physical arm simply leaves the sibling
# IDLE (no interferer) instead.
#
# Env: RT_CPU (required), FORCE (must be 1), SYS (default /sys).
# =============================================================================
set -euo pipefail
SYS="${SYS:-/sys}"
log() { echo "[offline-sibling] $*" >&2; }
die() { echo "FATAL: $*" >&2; exit 1; }

[[ "${FORCE:-0}" == "1" ]] || die "refusing to offline without FORCE=1 (NOT Azure-safe)"
[[ -n "${RT_CPU:-}" ]] || die "RT_CPU (the RT core's logical cpu) is required"

tsl="$SYS/devices/system/cpu/cpu${RT_CPU}/topology/thread_siblings_list"
[[ -r "$tsl" ]] || die "cannot read $tsl"
raw="$(cat "$tsl")"
sibling=""
IFS=',' read -ra parts <<< "$raw"
for p in "${parts[@]}"; do
  if [[ "$p" == *-* ]]; then a="${p%-*}"; b="${p#*-}"; for ((i=a;i<=b;i++)); do [[ "$i" != "$RT_CPU" ]] && sibling="$i"; done
  else [[ "$p" != "$RT_CPU" ]] && sibling="$p"; fi
done
[[ -n "$sibling" ]] || { log "cpu${RT_CPU} has no HT sibling (already a whole core); nothing to offline"; exit 0; }

f="$SYS/devices/system/cpu/cpu${sibling}/online"
[[ -w "$f" ]] || die "cannot write $f (need privileged)"
if [[ "$(cat "$f")" == "0" ]]; then log "cpu${sibling} already offline"; else echo 0 > "$f"; log "cpu${sibling} (sibling of RT cpu${RT_CPU}) set OFFLINE"; fi
