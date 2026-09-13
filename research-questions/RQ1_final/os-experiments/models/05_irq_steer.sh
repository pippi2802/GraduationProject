#!/usr/bin/env bash
# 05_irq_steer.sh <namespace> <status|apply|restore> [keep_cpu]
#
# OS-sensitivity scenario: steer every steerable device IRQ onto keep_cpu,
# install a boot-persistent systemd unit (kernel resets /proc/irq/* affinity
# on every boot regardless). No reboot needed either direction.
set -euo pipefail
NS="${1:?usage: 05_irq_steer.sh <namespace> <status|apply|restore> [keep_cpu]}"
MODE="${2:?usage: 05_irq_steer.sh <namespace> <status|apply|restore> [keep_cpu]}"
KEEP="${3:-0}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[05_irq_steer] ns=$NS agent=$AGENT mode=$MODE keep_cpu=$KEEP"

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" "$KEEP" <<'CORE'
set -u
MODE="$1"; KEEP="$2"
IRQ_UNIT=/etc/systemd/system/rq1-os-sensitivity-irq-steer.service

status() {
  echo "--- IRQ steering unit ---"
  systemctl is-enabled rq1-os-sensitivity-irq-steer.service 2>/dev/null || echo "not installed"
  echo "--- IRQs still allowed off keep_cpu ---"
  for f in /proc/irq/*/smp_affinity_list; do
    v=$(cat "$f" 2>/dev/null)
    [ "$v" = "$KEEP" ] || echo "$f: $v"
  done
}
apply() {
  for f in /proc/irq/*/smp_affinity_list; do
    echo "$KEEP" > "$f" 2>/dev/null || true
  done
  cat > "$IRQ_UNIT" <<EOF
[Unit]
Description=RQ1_final os-sensitivity -- steer all device IRQs onto cpu$KEEP at boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'for f in /proc/irq/*/smp_affinity_list; do echo $KEEP > "\$f" 2>/dev/null || true; done'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now rq1-os-sensitivity-irq-steer.service
  echo "IRQs steered onto cpu$KEEP now, persisted across future boots."
}
restore() {
  systemctl disable --now rq1-os-sensitivity-irq-steer.service 2>/dev/null || true
  rm -f "$IRQ_UNIT"
  systemctl daemon-reload
  echo "IRQ steering unit removed (existing affinity left as-is, not reset)."
}
case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: <status|apply|restore>"; exit 2 ;;
esac
CORE
