#!/usr/bin/env bash
# Build the node-prep script ConfigMap from the scripts, then apply the DaemonSet.
# Re-run after editing either script (no image rebuild needed).
set -euo pipefail
cd "$(dirname "$0")"

kubectl create namespace model1 --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap model1-node-prep-scripts -n model1 \
  --from-file=prepare-node.sh=prepare-node.sh \
  --from-file=restore-node.sh=restore-node.sh \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f node-prep-daemonset.yaml
echo "Applied. Ensure your RT node is labelled:  kubectl label node <NODE> model1/rt-node=true"
