#!/usr/bin/env bash
# Build the node-prep ConfigMap from the scripts and apply the DaemonSet.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NS=model3
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NS" create configmap model3-node-prep-scripts \
  --from-file="$HERE/detect-siblings.sh" \
  --from-file="$HERE/offline-sibling.sh" \
  --from-file="$HERE/online-siblings.sh" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$HERE/node-prep-daemonset.yaml"
kubectl -n "$NS" rollout status ds/model3-node-prep --timeout=120s || true
echo "[apply] node-prep applied. Verify: kubectl -n $NS logs ds/model3-node-prep"
echo "[apply] CPU map (per-core siblings): kubectl -n $NS exec ds/model3-node-prep -- cat /host/var/lib/model3/cpu-map.json"
