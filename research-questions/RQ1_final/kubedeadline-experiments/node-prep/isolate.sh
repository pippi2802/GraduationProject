#!/usr/bin/env bash
# isolate.sh <model> <status|apply|restore> [keep_cpu]  -- CPU core isolation
# (isolcpus/nohz_full/rcu_nocbs) for the model's node, via the rq1-agent DaemonSet
# + nsenter into the host (the agent is already privileged+hostPID from apply.sh,
# which is exactly what `nsenter --target 1` needs -- no new mounts/pods required).
#
#   bash node-prep/apply.sh model1                 # agent must already be up
#   bash node-prep/isolate.sh model1 apply         # stage the grub change (no reboot)
#   <reboot the node yourself: Azure Portal / az vm restart / ssh + `sudo reboot`>
#   bash node-prep/isolate.sh model1 status        # confirm isolcpus took effect
#
# keep_cpu (default 0) is left OUTSIDE isolation for kubelet/sshd/housekeeping --
# do not PIN_RTCPU / place a target onto keep_cpu once isolation is active.
#
# This changes host BOOT configuration and only takes effect after a reboot --
# rebooting drops every pod currently on that node. Read the printed output before
# rebooting anything; use 'restore' to undo (also needs a reboot to take effect).
set -euo pipefail
MODEL="${1:?usage: isolate.sh <model> <status|apply|restore> [keep_cpu]}"
MODE="${2:?usage: isolate.sh <model> <status|apply|restore> [keep_cpu]}"
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

echo "[isolate] model=$MODEL ns=$NS agent=$AGENT mode=$MODE keep_cpu=$KEEP"
kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" "$KEEP" < isolate-core.sh

if [ "$MODE" = "apply" ] || [ "$MODE" = "restore" ]; then
  echo
  echo "[isolate] >>> boot config staged on the node -- nothing takes effect until you reboot it. <<<"
  echo "[isolate] this will evict every pod currently on that node; make sure nothing is mid-run."
  echo "[isolate] reboot the underlying VM (Azure Portal / az vm restart / ssh + sudo reboot), then:"
  echo "[isolate]   bash node-prep/isolate.sh $MODEL status"
fi
