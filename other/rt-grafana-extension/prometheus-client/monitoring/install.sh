#!/usr/bin/env bash
# Install the standalone Prometheus + Grafana demo stack and load the dashboard.
# Run as azureuser on the control plane.
set -euo pipefail

cd "$(dirname "$0")"

echo ">> creating namespace + Prometheus"
kubectl apply -f prometheus.yaml

echo ">> creating Grafana dashboard ConfigMap from JSON"
kubectl -n rt-monitoring create configmap grafana-dashboard-rtdra \
  --from-file=rtdra-nas-dashboard.json=../dashboards/rtdra-nas-dashboard.json \
  --dry-run=client -o yaml | kubectl apply -f -

echo ">> creating Grafana"
kubectl apply -f grafana.yaml

echo ">> waiting for rollouts"
kubectl -n rt-monitoring rollout status deploy/prometheus --timeout=180s
kubectl -n rt-monitoring rollout status deploy/grafana --timeout=180s

cat <<'EOF'

>> Stack ready. Access the UIs via port-forward (run on the control plane):

   # Grafana  (login admin / admin) — dashboard: rt-DRA folder
   kubectl -n rt-monitoring port-forward svc/grafana 3000:3000

   # Prometheus
   kubectl -n rt-monitoring port-forward svc/prometheus 9090:9090

   From your laptop, tunnel through the bastion/SSH to localhost:3000.
EOF
