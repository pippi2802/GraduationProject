#!/usr/bin/env bash
# Build the node-prep ConfigMap from the scripts and apply the DaemonSet.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NS=model2
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NS" create configmap model2-node-prep-scripts \
  --from-file="$HERE/offline-siblings.sh" --from-file="$HERE/online-siblings.sh" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$HERE/node-prep-daemonset.yaml"
kubectl -n "$NS" rollout status ds/model2-node-prep --timeout=120s || true
echo "[apply] node-prep applied. Verify: kubectl -n $NS logs ds/model2-node-prep"
