#!/usr/bin/env bash
# Deploy the rt-DRA NAS exporter into the cluster.
# Run as azureuser on the control plane (kubectl configured there).
set -euo pipefail

cd "$(dirname "$0")"

echo ">> applying RBAC"
kubectl apply -f deploy/rbac.yaml

echo ">> applying Deployment + Service"
kubectl apply -f deploy/deployment.yaml

# Apply the ServiceMonitor only if the Prometheus Operator CRD is present.
if kubectl get crd servicemonitors.monitoring.coreos.com >/dev/null 2>&1; then
  echo ">> Prometheus Operator detected — applying ServiceMonitor"
  kubectl apply -f deploy/servicemonitor.yaml
else
  echo ">> No ServiceMonitor CRD; relying on prometheus.io/scrape pod annotations"
fi

echo ">> waiting for rollout"
kubectl -n dra-rt-driver rollout status deploy/rtdra-nas-exporter --timeout=120s

echo ">> exporter pods:"
kubectl -n dra-rt-driver get pods -l app=rtdra-nas-exporter -o wide

cat <<'EOF'

>> Quick check (port-forward the metrics endpoint):
   kubectl -n dra-rt-driver port-forward svc/rtdra-nas-exporter 9101:9101 &
   curl -s localhost:9101/metrics | grep rtdra_
EOF
