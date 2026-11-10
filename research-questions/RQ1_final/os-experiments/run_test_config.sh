#!/usr/bin/env bash
# run_test_config.sh <config> <node> [round]
#
# Re-run one configuration of the RQ1 os-experiments into test-results/, with the
# full-isolation calibration (use_full_isolation_k.sh) and only U in U_LIST.
# Single-core first, then multi-core, sequentially on <node>.
#
#   <config>  full | 01 | 02 | 03 | 04 | 05 | 06 | 08
#   <node>    kubernetes node this configuration is installed on (e.g. rt-k8s-worker-6)
#   [round]   default 1 -> OUT_TAG=_round1
#
# The node must already be in the configuration's boot/isolation state; this script
# does not change it. Run in the background:
#   nohup ./run_test_config.sh 02 rt-k8s-worker-7 1 > test-results/logs/driver_02_round1.log 2>&1 &
#
# DRY=1 prints what would run.
set -uo pipefail
CONFIG="${1:?usage: run_test_config.sh <full|01..08> <node> [round]}"
NODE="${2:?node name}"
ROUND="${3:-1}"
cd "$(dirname "$0")"

U_LIST="${U_LIST:-0.1,0.5,0.7,0.94}"
export RESULTS_ROOT="test-results/results" U_LIST OUT_TAG="_round${ROUND}"
LOGS="test-results/logs"; mkdir -p "$LOGS" "$RESULTS_ROOT"

if [ "$CONFIG" = full ]; then MODELS=(model1 model5-phys)
else MODELS=("${CONFIG}-model1" "${CONFIG}-model5"); fi

for m in "${MODELS[@]}"; do
  [ -f "workloads/$m/config.yaml" ] || { echo "no workloads/$m"; exit 1; }
  label=$(python3 -c "import yaml,sys;print(yaml.safe_load(open('workloads/$m/config.yaml'))['node_label'])")
  log="$LOGS/run_${m}_round${ROUND}.log"
  echo "[driver] $(date -Is) $m on $NODE label=$label U_LIST=$U_LIST -> $RESULTS_ROOT/${m}${OUT_TAG}"
  if [ "${DRY:-0}" = 1 ]; then echo "  kubectl label node $NODE $label --overwrite; ./apply.sh $m; ./run_job.sh $m > $log"; continue; fi
  kubectl label node "$NODE" "$label" --overwrite || exit 1
  ./apply.sh "$m" || exit 1
  ./run_job.sh "$m" > "$log" 2>&1
  echo "[driver] $(date -Is) $m finished (exit $?)"
  grep -E "did not produce valid data|^\s+- (soft|tight)/" "$log" || echo "[driver] $m: all cells valid"
done
echo "[driver] $(date -Is) $CONFIG done"
