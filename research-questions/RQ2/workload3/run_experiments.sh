#!/usr/bin/env bash
# run_experiments.sh        (run from the RQ2 folder; detach it: nohup workload3/run_experiments.sh > /dev/null 2>&1 &)
#
# Profiling node : baseline1, cache, memory, baseline2   -> workload3/results/<model>/<condition>/
# Swapped node   : baseline, memory                      -> workload3/alpha_drift/results/<vm>/<model>/<condition>/
# single_core is profiled on worker6 and swapped to worker7, multi_core on worker7 and swapped to worker6. The two models run
# at the same time on different nodes, one phase after the other (profiling, then swapped), so a node never runs both.
# Enemies as in workload/run_campaign.sh (start script confirms they burn cpu, stop script confirms they are gone).
# JOBS=<n> (default 100000, ~17 min a run), PHASES="profile swap", ONLY=single_core|multi_core limit what runs.
set -uo pipefail
cd "$(dirname "$0")/.."
JOBS="${JOBS:-100000}"; PHASES="${PHASES:-profile swap}"; ONLY="${ONLY:-single_core multi_core}"
CACHE_KB=266240; MEM_KB=2662400; STRIDE=64
mkdir -p workload3/results
declare -A PROFILE_VM=([single_core]=worker6 [multi_core]=worker7) SWAP_VM=([single_core]=worker7 [multi_core]=worker6)
declare -A POD=([single_core]=rq2-single-instance0 [multi_core]=rq2-multi) ENEMY_CPUS=([single_core]=2,3,0 [multi_core]=3,0)
declare -A INSTANCES=([single_core]="instance0" [multi_core]="instance0 instance1")

phase() {   # phase <model> <vm> <out root> <condition[:enemy KB]>...
    model=$1; vm=$2; out=$3; shift 3          # plain variables: phase runs in its own subshell, and the EXIT trap needs them
    ns=rq2-node-prep-$vm; node=rt-k8s-worker-${vm#worker}; log=workload3/results/${model}_experiments.log
    say() { printf '[%s] %s %s\n' "$(date -u +%H:%M:%S)" "$model@$vm" "$*" | tee -a "$log"; }
    agent=$(kubectl -n "$ns" get pod -l app=rq1-agent --field-selector "spec.nodeName=$node" -o jsonpath='{.items[0].metadata.name}')
    [ -n "$agent" ] || { say "FATAL no node-prep agent for $node in $ns"; return 1; }
    host=$(kubectl get node "$node" -o jsonpath='{.metadata.labels.kubernetes\.io/hostname}')
    on_node() { kubectl -n "$ns" exec -i "$agent" -- nsenter --target 1 --mount -- bash -s -- "$@"; }
    stop() { on_node < stress1/campaign_stop_enemies.sh 2>&1 | tee -a "$log" | grep -q STILL_ALIVE && say "FATAL enemy not stopped on $node"; }
    trap stop EXIT; trap 'exit 130' INT TERM            # whatever happens, no enemy is left running
    stop                                                  # clean start

    for spec in "$@"; do
        cond=${spec%%:*}; kb=${spec#*:}; [ "$kb" = "$spec" ] && kb=""
        say "=== $cond ($JOBS jobs)"
        [ -n "$kb" ] && { on_node "$kb" $STRIDE "${ENEMY_CPUS[$model]}" < stress1/campaign_start_enemies.sh 2>&1 | tee -a "$log" | grep -qE "MISSING|LOW_CPU" && { say "FATAL enemy not running"; stop; return 1; }; }
        sed -E -e "s#^([[:space:]]*)nodeSelector:.*#\1nodeSelector: { experiment-model: rq2, kubernetes.io/hostname: $host }#" \
               -e "s#jobs=[0-9]+#jobs=$JOBS#" workload3/pods/${model}_pod.yaml > "workload3/results/.${model}.yaml"
        ok=0
        for try in 1 2; do
            kubectl -n rq2 delete pod "${POD[$model]}" --ignore-not-found > /dev/null 2>&1
            kubectl apply -f "workload3/results/.${model}.yaml" > /dev/null 2>&1 \
              && OUT_ROOT="$out" NODE_PREP_NS="$ns" AGENT_POD="$agent" TIMEOUT="$((JOBS / 100 + 600))s" workload/pull_results.sh "$model" "$cond" >> "$log" 2>&1 \
              && check "$out/$model/$cond" && { ok=1; break; }
            say "attempt $try failed"
        done
        [ -n "$kb" ] && stop
        [ $ok = 1 ] && say "$cond done" || { say "$cond FAILED"; echo "$model@$vm $cond" >> workload3/results/failed.txt; }
        sleep 10
    done
}

check() {   # every instance: JOBS rows, FIFO + affinity + mlock really set
    local dir=$1 i
    for i in ${INSTANCES[$model]}; do
        [ "$(( $(wc -l < "$dir/$i.csv") - 1 ))" = "$JOBS" ] && python3 -c "
import json, sys
m = json.load(open(sys.argv[1])); sys.exit(0 if all(m[k] for k in ('mlockall_ok', 'sched_fifo_ok', 'affinity_ok')) else 1)" "$dir/$i.meta.json" || return 1
    done
}

rm -f workload3/results/failed.txt
for ph in $PHASES; do
    for model in $ONLY; do
        if [ "$ph" = profile ]; then
            ( phase "$model" "${PROFILE_VM[$model]}" workload3/results baseline1 "cache:$CACHE_KB" "memory:$MEM_KB" baseline2 ) &
        else
            vm=${SWAP_VM[$model]}
            ( phase "$model" "$vm" "workload3/alpha_drift/results/$vm" baseline "memory:$MEM_KB" ) &
        fi
    done
    wait
done
[ -s workload3/results/failed.txt ] && { echo "FAILED runs:"; cat workload3/results/failed.txt; exit 1; }
echo "all runs collected"
