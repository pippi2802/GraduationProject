#!/usr/bin/env bash
# Build the irq-control ConfigMap from the scripts and apply the DaemonSet.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NS=model4
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NS" create configmap model4-irq-control-scripts \
  --from-file="$HERE/steer.sh" --from-file="$HERE/restore.sh" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$HERE/irq-control-daemonset.yaml"
kubectl -n "$NS" rollout status ds/model4-irq-control --timeout=180s || true
echo "[apply] irq-control applied. run_model4.py will exec steer.sh/restore.sh into it."
echo "[apply] To restore manually: kubectl -n $NS exec ds/model4-irq-control -- bash /tmp/restore.sh"
