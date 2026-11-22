#!/usr/bin/env bash
# 05_irq_steer.sh <namespace> <status|apply|restore>
#
# SUBTRACTIVE: removes the IRQ steering the full baseline already applied
# (kubedeadline-experiments/node-prep/harden-core.sh's rq1-irq-steer.service),
# leaving everything else (isolcpus/nohz_full/rcu_nocbs, systemd-contain,
# boot-params) as baseline. Existing IRQ affinity is left as-is on removal
# (not actively reset), matching harden-core.sh's own restore_all() behavior.
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
IRQ_UNIT=/etc/systemd/system/rq1-irq-steer.service

status() {
  echo "--- IRQ steering unit (should be REMOVED for this scenario) ---"
  systemctl is-enabled rq1-irq-steer.service 2>/dev/null || echo "not installed"
}

apply() {  # remove -- baseline's own unit
  systemctl disable --now rq1-irq-steer.service 2>/dev/null || true
  rm -f "$IRQ_UNIT"
  systemctl daemon-reload
  echo "removed IRQ steering unit (existing affinity left as-is, not reset)."
}

restore() {  # put it back -- exactly as harden-core.sh's irq_steer() does
  for f in /proc/irq/*/smp_affinity_list; do
    echo "$KEEP" > "$f" 2>/dev/null || true
  done
  cat > "$IRQ_UNIT" <<EOF
[Unit]
Description=RQ1_final -- steer all device IRQs onto cpu$KEEP at boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'for f in /proc/irq/*/smp_affinity_list; do echo $KEEP > "\$f" 2>/dev/null || true; done'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now rq1-irq-steer.service
  echo "restored IRQ steering (onto cpu$KEEP) -- back to full baseline."
}

case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: <status|apply|restore>"; exit 2 ;;
esac
CORE
