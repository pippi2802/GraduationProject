#!/usr/bin/env bash
# 04_systemd_contain.sh <namespace> <status|apply|restore> [keep_cpu]
#
# OS-sensitivity scenario: clamp system.slice/user.slice to keep_cpu only via
# cgroup v2 AllowedCPUs= (kubepods.slice, where target pods live, is left
# untouched). No reboot needed either direction.
set -euo pipefail
NS="${1:?usage: 04_systemd_contain.sh <namespace> <status|apply|restore> [keep_cpu]}"
MODE="${2:?usage: 04_systemd_contain.sh <namespace> <status|apply|restore> [keep_cpu]}"
KEEP="${3:-0}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[04_systemd_contain] ns=$NS agent=$AGENT mode=$MODE keep_cpu=$KEEP"

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" "$KEEP" <<'CORE'
set -u
MODE="$1"; KEEP="$2"
DROPIN_DIR_SYS=/etc/systemd/system/system.slice.d
DROPIN_DIR_USR=/etc/systemd/system/user.slice.d

status() {
  echo "--- systemd containment ---"
  systemctl show system.slice -p AllowedCPUs 2>/dev/null
  systemctl show user.slice -p AllowedCPUs 2>/dev/null
}
apply() {
  mkdir -p "$DROPIN_DIR_SYS" "$DROPIN_DIR_USR"
  printf '[Slice]\nAllowedCPUs=%s\n' "$KEEP" > "$DROPIN_DIR_SYS/rq1-os-sensitivity.conf"
  printf '[Slice]\nAllowedCPUs=%s\n' "$KEEP" > "$DROPIN_DIR_USR/rq1-os-sensitivity.conf"
  systemctl daemon-reload
  systemctl set-property system.slice AllowedCPUs="$KEEP"
  systemctl set-property user.slice AllowedCPUs="$KEEP"
  echo "system.slice + user.slice clamped to cpu$KEEP (kubepods.slice untouched)."
}
restore() {
  rm -f "$DROPIN_DIR_SYS/rq1-os-sensitivity.conf" "$DROPIN_DIR_USR/rq1-os-sensitivity.conf"
  systemctl daemon-reload
  systemctl set-property system.slice AllowedCPUs="" 2>/dev/null || true
  systemctl set-property user.slice AllowedCPUs="" 2>/dev/null || true
  echo "systemd containment removed."
}
case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: <status|apply|restore>"; exit 2 ;;
esac
CORE
