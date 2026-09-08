#!/usr/bin/env bash
# Apply the node agent (results reader, + frequency pinning unless disabled)
# for one model.
#   ./apply.sh <model>              # normal: pins governor/turbo/freq
#   SKIP_FREQ_PIN=1 ./apply.sh <model>   # leaves frequency untouched (e.g.
#                                        # for an unmodified "before" baseline)
# Derives namespace / node label / host_path from models/<model>/config.yaml.
set -euo pipefail
MODEL="${1:?usage: apply.sh <model>}"
SKIP_FREQ_PIN="${SKIP_FREQ_PIN:-0}"
cd "$(dirname "$0")"

read -r NS LK LV HOST_PATH < <(python3 - "$MODEL" <<'PY'
import sys, yaml
c = yaml.safe_load(open(f"../models/{sys.argv[1]}/config.yaml"))
k, _, v = c["node_label"].partition("=")
print(c["namespace"], k, v, c["host_path"])
PY
)

echo "[node-prep] model=$MODEL ns=$NS label=$LK=$LV host_path=$HOST_PATH skip_freq_pin=$SKIP_FREQ_PIN"
sed -e "s|@@NS@@|$NS|g" \
    -e "s|@@LK@@|$LK|g" \
    -e "s|@@LV@@|$LV|g" \
    -e "s|@@HOST_PATH@@|$HOST_PATH|g" \
    -e "s|@@SKIP_FREQ_PIN@@|$SKIP_FREQ_PIN|g" \
    agent-daemonset.yaml.template | kubectl apply -f -

kubectl rollout status -n "$NS" ds/rq1-agent --timeout=120s
echo "[node-prep] agent up. Verify frequency pin:"
echo "  kubectl -n $NS exec ds/rq1-agent -- cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
