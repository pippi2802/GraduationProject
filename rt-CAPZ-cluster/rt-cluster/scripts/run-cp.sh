#!/bin/bash
# -----------------------------------------------------------------------------
# run-cp.sh
#
# Single entrypoint for a control-plane VM. Designed to be dropped into Azure
# cloud-init `customData` (or `runcmd`) -- it just chains the per-phase scripts
# in the right order and inherits all of their idempotency markers.
#
# Each phase exits 0 if its marker already exists, so re-running this script
# after a reboot or a partial failure is safe.
# -----------------------------------------------------------------------------
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${SCRIPT_DIR}/prereq-common.sh"
bash "${SCRIPT_DIR}/common.sh"
bash "${SCRIPT_DIR}/control-plane-init.sh"

echo
echo "[run-cp] all phases complete."
echo "[run-cp] worker join command: /var/lib/kubeadm-join.sh"
