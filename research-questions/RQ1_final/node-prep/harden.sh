#!/usr/bin/env bash
# harden.sh <model> <status|systemd-contain|irq-steer|boot-params|smt-off|restore-all> [keep_cpu]
#
# The extra isolation hardening beyond isolate.sh's isolcpus/nohz_full/rcu_nocbs:
# systemd cgroup containment, permanent IRQ steering, mitigations=off +
# transparent_hugepage=never, and SMT off. Same nsenter-via-agent technique as
# isolate.sh -- run node-prep/apply.sh <model> first if the agent isn't up yet.
#
#   bash node-prep/harden.sh model1 systemd-contain   # no reboot
#   bash node-prep/harden.sh model1 irq-steer         # no reboot
#   bash node-prep/harden.sh model1 boot-params       # stages grub -- REBOOT after
#   bash node-prep/harden.sh model1 smt-off           # no reboot, renumbers cores
#   bash node-prep/harden.sh model1 status            # dump current state of all
#   bash node-prep/harden.sh model1 restore-all       # undo everything above
#
# Do each one separately and snapshot with node-prep/isolation-audit.sh between
# them if you want per-action attribution rather than one lumped comparison.
# keep_cpu (default 0) must match whatever you used for isolate.sh -- everything
# here is clamped to that same core, never touching kubepods.slice (target/
# competitor pods live there and need cores 1-3).
set -euo pipefail
MODEL="${1:?usage: harden.sh <model> <status|systemd-contain|irq-steer|boot-params|smt-off|restore-all> [keep_cpu]}"
MODE="${2:?usage: harden.sh <model> <status|systemd-contain|irq-steer|boot-params|smt-off|restore-all> [keep_cpu]}"
KEEP="${3:-0}"
cd "$(dirname "$0")"

read -r NS < <(python3 - "$MODEL" <<'PY'
import sys, yaml
c = yaml.safe_load(open(f"../models/{sys.argv[1]}/config.yaml"))
print(c["namespace"])
PY
)
AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no node agent in $NS; run node-prep/apply.sh $MODEL first" >&2; exit 1; }

echo "[harden] model=$MODEL ns=$NS agent=$AGENT mode=$MODE keep_cpu=$KEEP"
kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" "$KEEP" < harden-core.sh

case "$MODE" in
  boot-params)
    echo
    echo "[harden] >>> boot config staged -- nothing takes effect until you reboot it. <<<"
    echo "[harden] this will evict every pod currently on that node; make sure nothing is mid-run."
    echo "[harden] reboot the underlying VM, then: bash node-prep/harden.sh $MODEL status"
    ;;
  restore-all)
    echo
    echo "[harden] systemd-contain/irq-steer/smt-off reverted immediately."
    echo "[harden] boot-params reversal still needs a reboot to take effect."
    ;;
esac
