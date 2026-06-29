#!/bin/bash
# -----------------------------------------------------------------------------
# run-worker.sh
#
# Single entrypoint for a worker VM. Suitable for cloud-init `customData` or
# `runcmd`. Runs phases 0-3, then phase 4b (worker-init.sh) which auto-runs
# /tmp/kubeadm-join.sh if you've already placed it; otherwise it prints
# instructions and exits 0.
# -----------------------------------------------------------------------------
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${SCRIPT_DIR}/prereq-common.sh"
bash "${SCRIPT_DIR}/common.sh"
bash "${SCRIPT_DIR}/worker-init.sh"

echo
echo "[run-worker] prerequisites + RT runtime installed."
echo "[run-worker] If the node has not joined yet, scp /var/lib/kubeadm-join.sh"
echo "[run-worker] from the control plane to /tmp/kubeadm-join.sh and re-run"
echo "[run-worker] this script (or just: sudo bash /tmp/kubeadm-join.sh)."
