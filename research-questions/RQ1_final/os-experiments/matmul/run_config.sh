#!/usr/bin/env bash
# run_config.sh <config> <node> [round]
#
# Runs one configuration, single-core then multi-core, into test-results/.
#   <config>  full | 01 | 02 | 03 | 04 | 05 | 06 | 08
#   <node>    node this configuration is installed on (used only for the relabel
#             between the two workloads)
#   [round]   default 1  ->  OUT_TAG=_round1
#
# BEFORE running (you do this): node configured + rebooted + rt-budget-seed.sh.
#
# Between workloads the script switches the node label and agent (different
# namespace per model). It does this for the SINGLE-core model too, at the start
# of EVERY round: after a round the node is left on the multi-core label, so
# without this, rounds 2+ found no single-core agent and skipped the single-core
# model. It stops the round if a model produced no "[run] done." line.
set -uo pipefail
CONFIG="${1:?usage: run_config.sh <full|01..08> <node> [round]}"
NODE="${2:?node name}"
ROUND="${3:-1}"
cd "$(dirname "$0")"

export RESULTS_ROOT="test-results/results" OUT_TAG="_round${ROUND}"
mkdir -p test-results/logs "$RESULTS_ROOT"

if [ "$CONFIG" = full ]; then SINGLE=model1; MULTI=model5-phys
else SINGLE="${CONFIG}-model1"; MULTI="${CONFIG}-model5"; fi

# switch to the single-core model: its node label + agent (idempotent in round 1)
slabel=$(python3 -c "import yaml;print(yaml.safe_load(open('workloads/$SINGLE/config.yaml'))['node_label'])")
kubectl label node "$NODE" "$slabel" --overwrite || exit 1
./apply.sh "$SINGLE" || exit 1

echo "[driver] $(date -Is) $SINGLE"
./run_job.sh "$SINGLE" > "test-results/logs/run_${SINGLE}_round${ROUND}.log" 2>&1
echo "[driver] $(date -Is) $SINGLE finished (exit $?)"
grep -E "^\[run\] done\." "test-results/logs/run_${SINGLE}_round${ROUND}.log" \
  || { echo "[driver] $SINGLE round ${ROUND}: no 'done.' line -- stopping"; exit 1; }

# switch to the multi-core model: its node label + agent
label=$(python3 -c "import yaml;print(yaml.safe_load(open('workloads/$MULTI/config.yaml'))['node_label'])")
kubectl label node "$NODE" "$label" --overwrite || exit 1
./apply.sh "$MULTI" || exit 1

echo "[driver] $(date -Is) $MULTI"
./run_job.sh "$MULTI" > "test-results/logs/run_${MULTI}_round${ROUND}.log" 2>&1
echo "[driver] $(date -Is) $MULTI finished (exit $?)"
grep -E "^\[run\] done\." "test-results/logs/run_${MULTI}_round${ROUND}.log" \
  || { echo "[driver] $MULTI round ${ROUND}: no 'done.' line -- stopping"; exit 1; }
echo "[driver] $(date -Is) config $CONFIG done"
