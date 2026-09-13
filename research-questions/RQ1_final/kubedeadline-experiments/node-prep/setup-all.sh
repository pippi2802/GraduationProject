#!/usr/bin/env bash
# setup-all.sh <model> [keep_cpu] -- run every node-prep step in one go:
# frequency pin + node agent, core isolation (isolcpus/nohz_full/rcu_nocbs),
# and the second hardening round (systemd-contain, irq-steer, boot-params).
#
# Deliberately does NOT reboot for you -- isolate.sh's isolcpus/nohz_full/
# rcu_nocbs and harden.sh's boot-params both stage into the SAME grub line,
# so everything here converges on ONE reboot at the end instead of one per
# script. systemd-contain and irq-steer take effect immediately (no reboot
# needed for those specifically), boot-params needs the reboot to activate.
#
#   bash node-prep/setup-all.sh model1
#   <reboot the node yourself: Azure Portal / az vm restart / ssh + sudo reboot>
#   bash node-prep/isolate.sh model1 status
#   bash node-prep/harden.sh model1 status
#
# Run node-prep/isolation-audit.sh's own "before" snapshot BEFORE calling
# this, and "after" once the node is back up post-reboot, if you want the
# before/after impact measurement -- see its own header for the exact
# sequence. Not folded in here since it needs sudo directly on the node
# (not routed through the k8s agent like everything else in this script).
set -euo pipefail
MODEL="${1:?usage: setup-all.sh <model> [keep_cpu]}"
KEEP="${2:-0}"
cd "$(dirname "$0")"

echo "[setup-all] === 1/5: node agent + frequency pin ==="
bash apply.sh "$MODEL"

echo
echo "[setup-all] === 2/5: core isolation (isolcpus/nohz_full/rcu_nocbs) -- staged, needs reboot ==="
bash isolate.sh "$MODEL" apply "$KEEP"

echo
echo "[setup-all] === 3/5: systemd cgroup containment -- takes effect now ==="
bash harden.sh "$MODEL" systemd-contain "$KEEP"

echo
echo "[setup-all] === 4/5: IRQ steering -- takes effect now ==="
bash harden.sh "$MODEL" irq-steer "$KEEP"

echo
echo "[setup-all] === 5/5: boot params (mitigations=off, transparent_hugepage=never, rcu_nocb_poll) -- staged, needs reboot ==="
bash harden.sh "$MODEL" boot-params "$KEEP"

echo
echo "[setup-all] done staging. >>> REBOOT THE NODE NOW to activate isolcpus + boot-params. <<<"
echo "[setup-all] this evicts every pod currently on that node -- make sure nothing is mid-run."
echo "[setup-all] after reboot, verify with:"
echo "[setup-all]   bash node-prep/isolate.sh $MODEL status"
echo "[setup-all]   bash node-prep/harden.sh $MODEL status"
