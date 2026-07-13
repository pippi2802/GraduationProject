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

# ---------------------------------------------------------------------------
# RT budget setup (idempotent). WHY THIS EXISTS: this HCBS / RT_GROUP_SCHED
# kernel boots with kernel.sched_rt_runtime_us at an UNSAFE value (-1 or ==
# period) and with the root->kubepods->besteffort cpu.rt_runtime_us chain
# ZEROED. Until both are fixed, NO rt-DRA (KubeDeadline / SCHED_FIFO) pod can
# admit and an unthrottled FIFO task can wedge a core. This used to be a MANUAL
# step (only documented in rt-budget-reseed.service's header) that got forgotten
# -> nodes silently shipped with RT throttling disabled. Wire it into
# provisioning so EVERY worker is correct on every boot.
# See docs/OPEN-PROBLEMS-rt-dra.md and docs/FINDING-rtdra-offline-cpu-allocation.md.
install -m0644 "${SCRIPT_DIR}/60-rt-throttle.conf" /etc/sysctl.d/60-rt-throttle.conf
sysctl --system >/dev/null 2>&1 || true          # apply the safe global default now (early = no EBUSY)
install -m0755 "${SCRIPT_DIR}/rt-budget-reseed.sh"      /usr/local/sbin/rt-budget-reseed.sh
install -m0644 "${SCRIPT_DIR}/rt-budget-reseed.service" /etc/systemd/system/rt-budget-reseed.service
systemctl daemon-reload
systemctl enable rt-budget-reseed.service        # seeds the cgroup RT chain at boot (After=kubelet)

bash "${SCRIPT_DIR}/worker-init.sh"

echo
echo "[run-worker] prerequisites + RT runtime installed."
echo "[run-worker] If the node has not joined yet, scp /var/lib/kubeadm-join.sh"
echo "[run-worker] from the control plane to /tmp/kubeadm-join.sh and re-run"
echo "[run-worker] this script (or just: sudo bash /tmp/kubeadm-join.sh)."
