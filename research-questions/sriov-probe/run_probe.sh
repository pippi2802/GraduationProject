#!/usr/bin/env bash
set -euo pipefail

CONFIG_LABEL="${CONFIG_LABEL:?set CONFIG_LABEL=accel_on or accel_off}"
PING_COUNT="${PING_COUNT:-300}"
IPERF_SECONDS="${IPERF_SECONDS:-20}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${SCRIPT_DIR}/results/${CONFIG_LABEL}_$(date +%Y%m%dT%H%M%S)"
mkdir -p "${OUT_DIR}"

echo "== deploying server/client pods =="
kubectl apply -f "${SCRIPT_DIR}/server.yaml"
kubectl apply -f "${SCRIPT_DIR}/client.yaml"

kubectl wait --for=condition=Ready pod/sriov-probe-server --timeout=120s
kubectl wait --for=condition=Ready pod/sriov-probe-client --timeout=120s

SERVER_NODE=$(kubectl get pod sriov-probe-server -o jsonpath='{.spec.nodeName}')
SERVER_IP=$(kubectl get node "${SERVER_NODE}" -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}')
echo "server node=${SERVER_NODE} ip=${SERVER_IP}"
echo "${SERVER_IP}" > "${OUT_DIR}/server_ip.txt"

echo "== ping (${PING_COUNT} packets) =="
kubectl exec sriov-probe-client -- ping -c "${PING_COUNT}" "${SERVER_IP}" \
  | tee "${OUT_DIR}/ping.log"

echo "== iperf3 TCP throughput (${IPERF_SECONDS}s) =="
kubectl exec sriov-probe-client -- iperf3 -c "${SERVER_IP}" -t "${IPERF_SECONDS}" -J \
  > "${OUT_DIR}/iperf_tcp.json"

echo "== iperf3 UDP jitter (${IPERF_SECONDS}s) =="
kubectl exec sriov-probe-client -- iperf3 -c "${SERVER_IP}" -u -b 100M -t "${IPERF_SECONDS}" -J \
  > "${OUT_DIR}/iperf_udp.json"

echo "== cleaning up pods =="
kubectl delete -f "${SCRIPT_DIR}/client.yaml" --ignore-not-found
kubectl delete -f "${SCRIPT_DIR}/server.yaml" --ignore-not-found

echo "done -> ${OUT_DIR}"
