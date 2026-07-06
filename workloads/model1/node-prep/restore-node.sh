#!/usr/bin/env bash
# =============================================================================
# Model 1 node-prep RESTORE: bring the offlined hyper-thread siblings back
# online (undo prepare-node.sh). Reads the mapping written by prepare-node.sh.
#
# Env: MAP_OUT (default /var/lib/model1/cpu-map.json)
# =============================================================================
set -euo pipefail
SYS=/sys/devices/system/cpu
MAP_OUT="${MAP_OUT:-/var/lib/model1/cpu-map.json}"
log() { echo "[node-restore] $*" >&2; }

[[ -r "$MAP_OUT" ]] || { echo "no map at $MAP_OUT; nothing to restore" >&2; exit 0; }

# extract the offline_siblings array without a JSON parser dependency
sibs="$(grep -o '"offline_siblings": *\[[^]]*\]' "$MAP_OUT" | grep -o '[0-9]\+' || true)"
if [[ -z "$sibs" ]]; then
  log "no offlined siblings recorded"
  exit 0
fi
for c in $sibs; do
  f="$SYS/cpu$c/online"
  if [[ -w "$f" ]]; then
    echo 1 > "$f"
    log "cpu$c set online"
  else
    log "cannot write $f (need privileged/root)"
  fi
done
