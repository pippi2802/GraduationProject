#!/usr/bin/env bash
# 04_systemd_contain.sh <namespace> <status|apply|restore>
#
# SUBTRACTIVE: removes the systemd containment the full baseline already
# applied (kubedeadline-experiments/node-prep/harden-core.sh's
# rq1-harden.conf drop-ins on system.slice/user.slice), leaving everything
# else (isolcpus/nohz_full/rcu_nocbs, irq-steer, boot-params) as baseline.
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
DROPIN_SYS=/etc/systemd/system/system.slice.d/rq1-harden.conf
DROPIN_USR=/etc/systemd/system/user.slice.d/rq1-harden.conf

status() {
  echo "--- systemd containment (should be REMOVED for this scenario) ---"
  systemctl show system.slice -p AllowedCPUs 2>/dev/null
  systemctl show user.slice -p AllowedCPUs 2>/dev/null
}

apply() {  # remove containment -- baseline's own drop-ins.
  # Always clear both the drop-in files AND the live systemctl property --
  # `set-property` persists independently of the drop-in file's presence, so
  # checking file-existence alone (as this used to) can skip the actual
  # live-property clear when a prior run already removed just the file.
  rm -f "$DROPIN_SYS" "$DROPIN_USR"
  systemctl daemon-reload
  systemctl set-property system.slice AllowedCPUs="" 2>/dev/null || true
  systemctl set-property user.slice AllowedCPUs="" 2>/dev/null || true
  echo "removed systemd containment (system.slice/user.slice unclamped)."
}

restore() {  # put it back -- exactly as harden-core.sh's systemd_contain() does
  mkdir -p "$(dirname "$DROPIN_SYS")" "$(dirname "$DROPIN_USR")"
  printf '[Slice]\nAllowedCPUs=%s\n' "$KEEP" > "$DROPIN_SYS"
  printf '[Slice]\nAllowedCPUs=%s\n' "$KEEP" > "$DROPIN_USR"
  systemctl daemon-reload
  systemctl set-property system.slice AllowedCPUs="$KEEP"
  systemctl set-property user.slice AllowedCPUs="$KEEP"
  echo "restored systemd containment (clamped to cpu$KEEP) -- back to full baseline."
}

case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: <status|apply|restore>"; exit 2 ;;
esac
CORE
