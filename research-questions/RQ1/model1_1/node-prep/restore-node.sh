#!/usr/bin/env bash
# Restore any offlined sibling CPUs (only relevant if prepare-node ran with
# DRY_RUN=0). Detect-only default leaves nothing to restore.
set -euo pipefail
SYS=/sys/devices/system/cpu
log() { echo "[restore] $*" >&2; }
for d in "$SYS"/cpu[0-9]*; do
  f="$d/online"
  [[ -f "$f" ]] || continue
  if [[ "$(cat "$f")" == "0" ]]; then
    if [[ -w "$f" ]]; then echo 1 > "$f" && log "onlined ${d##*/}"; else log "cannot online ${d##*/}"; fi
  fi
done
log "done"
