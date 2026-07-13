#!/usr/bin/env bash
# =============================================================================
# Model 4 — IRQ STEER. Move steerable DEVICE IRQs onto (arm=on) or away from
# (arm=off) the RT core, pause irqbalance so affinity stays stable, and record what
# was ACTUALLY steerable (Azure-guest IRQ controllability is limited and NIC-
# dependent). Idempotent. Writes an irq-map.json for the harness to record per cell.
#
# The kernel exposes /proc/irq/<n>/smp_affinity_list as GLOBAL state, so a
# privileged container can write it and affect the host's IRQ routing. irqbalance
# (a host process) is PAUSED with SIGSTOP (hostPID) and resumed by restore.sh, so it
# does not fight our affinity during the run.
#
# Env:
#   ARM              off | on              (required)
#   RT_CPU           logical cpu of the RT core            (required)
#   OTHER_CPU        logical cpu of the OTHER physical core (required)
#   STEERABLE_REGEX  egrep pattern of device-IRQ descriptors (default virtio|hyperv|hv_|mlx|eth|nvme|storvsc|scsi)
#   MAP_OUT          default /host/var/lib/model4/irq-map.json
#   PROC             default /proc
# =============================================================================
set -euo pipefail
PROC="${PROC:-/proc}"
MAP_OUT="${MAP_OUT:-/host/var/lib/model4/irq-map.json}"
STEERABLE_REGEX="${STEERABLE_REGEX:-virtio|hyperv|hv_|mlx|eth|nvme|storvsc|scsi}"
log() { echo "[irq-steer] $*" >&2; }
die() { echo "FATAL: $*" >&2; exit 1; }

[[ -n "${ARM:-}" ]]       || die "ARM (off|on) required"
[[ -n "${RT_CPU:-}" ]]    || die "RT_CPU required"
[[ -n "${OTHER_CPU:-}" ]] || die "OTHER_CPU required"
[[ -r "$PROC/interrupts" ]] || die "cannot read $PROC/interrupts"

if [[ "$ARM" == "on" ]]; then TARGET="$RT_CPU"; else TARGET="$OTHER_CPU"; fi
log "arm=$ARM -> steer steerable IRQs to cpu$TARGET (RT=cpu$RT_CPU other=cpu$OTHER_CPU)"

# --- pause irqbalance so it does not undo our affinity --------------------------
IRQBALANCE_WAS_RUNNING=0
if pgrep -x irqbalance >/dev/null 2>&1; then
  IRQBALANCE_WAS_RUNNING=1
  pkill -STOP -x irqbalance 2>/dev/null && log "irqbalance paused (SIGSTOP)" || log "WARN could not pause irqbalance"
else
  log "irqbalance not running"
fi

# --- classify + steer IRQ lines --------------------------------------------------
steered=(); steered_desc=(); notsteer=()
# header line lists CPU columns; data lines: "<irq>: c0 c1 ... <desc>"
while IFS= read -r line; do
  irq="${line%%:*}"; irq="${irq//[[:space:]]/}"
  [[ "$irq" =~ ^[0-9]+$ ]] || continue                 # skip LOC/RES/IPI/etc (not steerable)
  desc="$(echo "$line" | sed -E 's/^[[:space:]]*[0-9]+:([[:space:]]+[0-9]+)+[[:space:]]*//')"
  aff="$PROC/irq/$irq/smp_affinity_list"
  [[ -w "$aff" ]] || { notsteer+=("$irq"); continue; }
  if echo "$desc" | grep -Eiq "$STEERABLE_REGEX"; then
    if echo "$TARGET" > "$aff" 2>/dev/null; then
      # verify it actually took (some lines silently reject / are managed)
      got="$(cat "$aff" 2>/dev/null || echo '?')"
      if [[ "$got" == "$TARGET" ]]; then steered+=("$irq"); steered_desc+=("$desc")
      else notsteer+=("$irq"); log "irq$irq ($desc) rejected affinity (managed?) -> got '$got'"; fi
    else notsteer+=("$irq"); log "irq$irq ($desc) write failed"; fi
  fi
done < "$PROC/interrupts"

log "steered ${#steered[@]} device IRQ line(s) to cpu$TARGET: ${steered[*]:-<none>}"
[[ ${#steered[@]} -eq 0 ]] && log "WARNING: NO device IRQ line was steerable (Azure guest limitation) — the harness preflight will decide whether to proceed."

# --- record the applied map ------------------------------------------------------
mkdir -p "$(dirname "$MAP_OUT")"
{
  printf '{\n  "arm": "%s",\n  "target_cpu": %s,\n  "rt_cpu": %s,\n  "other_cpu": %s,\n' "$ARM" "$TARGET" "$RT_CPU" "$OTHER_CPU"
  printf '  "irqbalance_was_running": %s,\n' "$IRQBALANCE_WAS_RUNNING"
  printf '  "steerable_regex": "%s",\n' "$STEERABLE_REGEX"
  printf '  "steered_irqs": [%s],\n' "$(IFS=,; echo "${steered[*]:-}")"
  printf '  "steered_count": %s,\n' "${#steered[@]}"
  printf '  "not_steerable_count": %s\n' "${#notsteer[@]}"
  printf '}\n'
} > "$MAP_OUT"
log "wrote $MAP_OUT"; cat "$MAP_OUT" >&2
