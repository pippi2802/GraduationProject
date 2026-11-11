#!/usr/bin/env bash
# run_config.sh <config> <node> [round]
#
# One configuration, single-core then multi-core, on <node>, into test-results/.
#   <config>  full | 01 | 02 | 03 | 04 | 05 | 06 | 08
#   <node>    node this configuration is installed on (e.g. rt-k8s-worker-6)
#   [round]   default 1  ->  OUT_TAG=_round1
#
# The node must already be in the configuration's state (check it with
# models/verify_scenario.sh first). Extra settings pass through the environment:
#   CV_THRESHOLD=0.1 U_MAX=0.7 ./run_config.sh 01 rt-k8s-worker-7 1
#
# Run in the background so it survives the terminal:
#   nohup ./run_config.sh 02 rt-k8s-worker-6 1 > test-results/logs/driver_02_round1.log 2>&1 &
set -uo pipefail
CONFIG="${1:?usage: run_config.sh <full|01..08> <node> [round]}"
NODE="${2:?node name}"
ROUND="${3:-1}"
cd "$(dirname "$0")"

export RESULTS_ROOT="test-results/results" OUT_TAG="_round${ROUND}"
mkdir -p test-results/logs "$RESULTS_ROOT"

if [ "$CONFIG" = full ]; then MODELS=(model1 model5-phys)
else MODELS=("${CONFIG}-model1" "${CONFIG}-model5"); fi

for m in "${MODELS[@]}"; do
  [ -f "workloads/$m/config.yaml" ] || { echo "[driver] no workloads/$m"; exit 1; }
  read -r ns label < <(python3 -c "import yaml;c=yaml.safe_load(open('workloads/$m/config.yaml'));print(c['namespace'],c['node_label'])")
  log="test-results/logs/run_${m}_round${ROUND}.log"
  echo "[driver] $(date -Is) $m  node=$NODE  ns=$ns  -> $RESULTS_ROOT/${m}${OUT_TAG}"

  kubectl label node "$NODE" "$label" --overwrite || exit 1
  ./apply.sh "$m" || exit 1

  # run_job.sh uses the FIRST agent pod of the namespace: it must be on $NODE
  agent_node=$(kubectl -n "$ns" get pod -l app=rq1-agent -o jsonpath='{.items[0].spec.nodeName}')
  if [ "$agent_node" != "$NODE" ]; then
    echo "[driver] ABORT: first agent in $ns is on '$agent_node', not '$NODE' (stale agent / old node label?)"; exit 1
  fi

  ./run_job.sh "$m" > "$log" 2>&1
  echo "[driver] $(date -Is) $m finished (exit $?)"
  grep -E "^\[run\] done\." "$log"
done
echo "[driver] $(date -Is) config $CONFIG done: ${MODELS[*]}"
