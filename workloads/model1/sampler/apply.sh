#!/usr/bin/env bash
# Build the sampler ConfigMap from sampler.py, then apply the DaemonSet.
# Re-run after editing sampler.py (no image rebuild needed).
set -euo pipefail
cd "$(dirname "$0")"

kubectl create namespace model1 --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap model1-sampler-script -n model1 \
  --from-file=sampler.py=sampler.py \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f sampler-daemonset.yaml
echo "Sampler applied. Logs: kubectl -n model1 logs ds/model1-sampler"
