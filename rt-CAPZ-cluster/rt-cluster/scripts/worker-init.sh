#!/bin/bash
# -----------------------------------------------------------------------------
# worker-init.sh
#
# Phase 4b (worker side).  By design the actual `kubeadm join` is performed
# MANUALLY, because we want you to read the join script before it runs.
#
# What this script does:
#   * sanity-checks that prereq-common.sh and common.sh have completed
#     (so RT-containerd, RT-runc, kubelet, kernel modules and sysctl are ready)
#   * verifies kubelet is not yet joined to a cluster
#   * if /tmp/kubeadm-join.sh exists (you `scp`ed it from the CP) it runs it
#   * otherwise it just prints the next manual step and exits 0
#
# Idempotent via /var/lib/rt-stack/markers/worker-init.done (marker is only
# written after a successful join).
# -----------------------------------------------------------------------------
set -Eeuo pipefail

# shellcheck source=lib/common-functions.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common-functions.sh"

rt_strict_mode
rt_setup_logging worker-init
rt_skip_if_done   worker-init

if ! rt_already_done prereq-common; then echo "[error] run prereq-common.sh first" >&2; exit 1; fi
if ! rt_already_done common;         then echo "[error] run common.sh first"         >&2; exit 1; fi

# Already joined?  /etc/kubernetes/kubelet.conf is written by kubeadm join.
if [[ -f /etc/kubernetes/kubelet.conf ]]; then
    echo "[join] /etc/kubernetes/kubelet.conf already present; node has joined"
    systemctl is-active --quiet kubelet || systemctl start kubelet
    rt_mark_done worker-init
    exit 0
fi

JOIN_SRC="${RT_JOIN_FILE:-/tmp/kubeadm-join.sh}"
if [[ -f "$JOIN_SRC" ]]; then
    echo "[join] $JOIN_SRC found, joining cluster"
    chmod 0700 "$JOIN_SRC"
    bash "$JOIN_SRC"
    rt_mark_done worker-init
    exit 0
fi

cat <<'EOF'
============================================================================
worker is provisioned (RT runtime + kubelet) but NOT yet joined.

To join this worker:

  1) On the control plane, the join command lives at:
         /var/lib/kubeadm-join.sh

  2) From your workstation (or via the CP), copy it onto this worker:
         scp azureuser@<CP-IP>:/var/lib/kubeadm-join.sh /tmp/kubeadm-join.sh
         # then on this worker, as root:
         sudo bash /tmp/kubeadm-join.sh

     (or re-run this script after placing the file at /tmp/kubeadm-join.sh
      and it will execute it for you.)

This script will write its done-marker the next time it successfully joins.
============================================================================
EOF
