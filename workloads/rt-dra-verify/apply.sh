#!/usr/bin/env bash
# Apply the RT-DRA verification workload.
# Builds the ConfigMap from verify.sh (single source of truth) then applies the
# pod + claim. Run from this directory (or any dir; paths are resolved here).
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
NS=rt-verify

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap rt-verify-script -n "$NS" \
  --from-file=verify.sh="${DIR}/verify.sh" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f "${DIR}/rt-verify.yaml"

cat <<EOF

Applied. Watch it come up:
  kubectl -n ${NS} get pod rt-verify -w

Read the report:
  kubectl -n ${NS} logs rt-verify

Re-run after editing verify.sh:
  kubectl -n ${NS} delete pod rt-verify --ignore-not-found
  ./apply.sh
EOF
