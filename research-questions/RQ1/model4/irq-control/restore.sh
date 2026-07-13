#!/usr/bin/env bash
# =============================================================================
# Model 4 — IRQ RESTORE. Undo steer.sh: set every writable /proc/irq/<n>/
# smp_affinity_list back to ALL online CPUs, and RESUME irqbalance if it was
# running (per the recorded irq-map.json). Idempotent; safe to run repeatedly.
# Env: PROC (default /proc), MAP_OUT (default /host/var/lib/model4/irq-map.json).
# =============================================================================
set -euo pipefail
PROC="${PROC:-/proc}"
MAP_OUT="${MAP_OUT:-/host/var/lib/model4/irq-map.json}"
log() { echo "[irq-restore] $*" >&2; }

# all online cpus, e.g. "0-3"
online="$(cat /sys/devices/system/cpu/online 2>/dev/null || echo 0-0)"
n=0
for d in "$PROC"/irq/[0-9]*; do
  aff="$d/smp_affinity_list"
  [[ -w "$aff" ]] || continue
  if echo "$online" > "$aff" 2>/dev/null; then n=$((n+1)); fi
done
log "restored default affinity ($online) on $n IRQ line(s)"

# resume irqbalance if steer.sh had paused it
was_running=1
if [[ -r "$MAP_OUT" ]]; then
  grep -q '"irqbalance_was_running": 0' "$MAP_OUT" && was_running=0 || true
fi
if pgrep -x irqbalance >/dev/null 2>&1; then
  pkill -CONT -x irqbalance 2>/dev/null && log "irqbalance resumed (SIGCONT)" || log "WARN could not resume irqbalance"
else
  [[ "$was_running" == "1" ]] && log "NOTE irqbalance was running before but is not visible now (may need host restart)" || log "irqbalance was not running; nothing to resume"
fi
log "done"
