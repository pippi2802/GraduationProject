#!/usr/bin/env bash
# run_config.sh <dNN> <node> [round]
#
# Runs one RQ1_fromdefault configuration on one VM: single-core (dNN-model1) then multi-core (dNN-model5), into results/.
#   <dNN>    d07 (all defaults, reference) | d01 isolcpus | d02 nohz_full | d03 rcu_nocbs | d04 systemd | d05 IRQ steering | d06 boot-params | d08 frequency pinning
#   <node>   node (VM) this configuration is installed on, used for the relabel of each workload
#   [round]  default 1 -> OUT_TAG=_round1
#
# BEFORE running (you do this, see README.md): the lever is applied (and the node rebooted if it needs that), levers/lever.sh status checked,
# rt-budget-seed.sh run, DRA driver up on the node.
# The script labels the node and deploys the agent for each workload itself. The agent is deployed with SKIP_FREQ_PIN=1 for every
# configuration except d08, so frequency stays at the OS default there (the agent pins it otherwise, see agent-daemonset.yaml.template).
# Env passed through to run_job.sh: U_MAX (e.g. U_MAX=0.7 for d07, U = 0.94 was not run in the all-defaults state of RQ1_final), CV_THRESHOLD, ...
set -uo pipefail
CODE="${1:?usage: run_config.sh <d01..d08> <node> [round]}"
NODE="${2:?node name}"
ROUND="${3:-1}"
cd "$(dirname "$0")"
export OUT_TAG="_round${ROUND}" RESULTS_ROOT="results"
mkdir -p logs results
if [ "$CODE" = d08 ]; then export SKIP_FREQ_PIN=0; else export SKIP_FREQ_PIN=1; fi

for MODEL in "${CODE}-model1" "${CODE}-model5"; do
  label=$(python3 -c "import yaml;print(yaml.safe_load(open('workloads/$MODEL/config.yaml'))['node_label'])")
  kubectl label node "$NODE" "$label" --overwrite || exit 1
  ./apply.sh "$MODEL" || exit 1
  echo "[driver] $(date -Is) $MODEL"
  ./run_job.sh "$MODEL" > "logs/run_${MODEL}_round${ROUND}.log" 2>&1
  echo "[driver] $(date -Is) $MODEL finished (exit $?)"
  grep -E "^\[run\] (done\.|FAILED)" "logs/run_${MODEL}_round${ROUND}.log"
done
echo "[driver] $(date -Is) config $CODE done on $NODE (round $ROUND)"
