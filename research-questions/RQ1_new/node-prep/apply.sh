#!/usr/bin/env bash
# Apply the node agent (frequency pinning + results reader) for one model.
#   ./apply.sh <model>
# Derives namespace / node label / host_path from models/<model>/config.yaml.
set -euo pipefail
MODEL="${1:?usage: apply.sh <model>}"
cd "$(dirname "$0")"

read -r NS LK LV HOST_PATH < <(python3 - "$MODEL" <<'PY'
import sys
sys.path.insert(0, "../common")
import rqlib
c = rqlib.load_config(sys.argv[1])
k, v = rqlib._label_kv(c)
print(c["namespace"], k, v, c["host_path"])
PY
)

echo "[node-prep] model=$MODEL ns=$NS label=$LK=$LV host_path=$HOST_PATH"
sed -e "s|@@NS@@|$NS|g" \
    -e "s|@@LK@@|$LK|g" \
    -e "s|@@LV@@|$LV|g" \
    -e "s|@@HOST_PATH@@|$HOST_PATH|g" \
    agent-daemonset.yaml.template | kubectl apply -f -

kubectl rollout status -n "$NS" ds/rq1-agent --timeout=120s
echo "[node-prep] agent up. Verify frequency pin:"
echo "  kubectl -n $NS exec ds/rq1-agent -- cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
