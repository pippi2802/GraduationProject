#!/usr/bin/env bash
# Build the node-prep ConfigMap from the scripts and apply the DaemonSet.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NS=model4
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NS" create configmap model4-node-prep-scripts \
  --from-file="$HERE/detect-siblings.sh" \
  --from-file="$HERE/offline-siblings.sh" \
  --from-file="$HERE/online-siblings.sh" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$HERE/node-prep-daemonset.yaml"
kubectl -n "$NS" rollout status ds/model4-node-prep --timeout=120s || true
echo "[apply] node-prep applied. CPU map: kubectl -n $NS exec ds/model4-node-prep -- cat /host/var/lib/model4/cpu-map.json"
