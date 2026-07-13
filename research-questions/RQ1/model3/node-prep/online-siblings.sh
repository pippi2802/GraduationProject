#!/usr/bin/env bash
# Model 3 — re-online any offlined sibling CPUs (undo offline-sibling.sh FORCE=1).
# Detect-only default leaves nothing to restore. Idempotent.
set -euo pipefail
SYS="${SYS:-/sys}"
log() { echo "[online-siblings] $*" >&2; }
for d in "$SYS"/devices/system/cpu/cpu[0-9]*; do
  f="$d/online"
  [[ -f "$f" ]] || continue
  if [[ "$(cat "$f")" == "0" ]]; then
    if [[ -w "$f" ]]; then echo 1 > "$f" && log "onlined ${d##*/}"; else log "cannot online ${d##*/}"; fi
  fi
done
log "done"
