#!/usr/bin/env bash
# Build the node-prep ConfigMap from the scripts and apply the DaemonSet.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NS=model1-1
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$NS" create configmap model1-1-node-prep-scripts \
  --from-file="$HERE/prepare-node.sh" --from-file="$HERE/restore-node.sh" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$HERE/node-prep-daemonset.yaml"
kubectl -n "$NS" rollout status ds/model1-1-node-prep --timeout=120s || true
echo "[apply] node-prep applied. Verify: kubectl -n $NS logs ds/model1-1-node-prep"
