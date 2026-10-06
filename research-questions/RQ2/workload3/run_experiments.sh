#!/usr/bin/env bash
# run_experiments.sh <profile|swap>     (run from the RQ2 folder; detach it: nohup workload3/run_experiments.sh profile > /dev/null 2>&1 &)
#
# profile : on the profiling node, baseline1, cache, memory, baseline2  -> workload3/results/<model>/<condition>/
# swap    : on the other node, baseline, memory                         -> workload3/alpha_drift/results/<vm>/<model>/<condition>/
# The two phases are independent: run one, work on its data, run the other later. Never both at once: they share the pod names
# and the nodes (single_core: profile on worker6, swap on worker7; multi_core: profile on worker7, swap on worker6), so the
# script refuses to start while a pod of this workload exists. Within a phase the two models run at the same time, on different nodes.
# Enemies as in workload/run_campaign.sh (start script confirms they burn cpu, stop script confirms they are gone).
# JOBS=<n> (default 100000, ~17 min a run), ONLY=single_core|multi_core limit what runs. Logs: workload3/results/<model>_<phase>.log
set -uo pipefail
cd "$(dirname "$0")/.."
PHASE="${1:?usage: run_experiments.sh <profile|swap>}"; [[ "$PHASE" =~ ^(profile|swap)$ ]] || { echo "phase must be profile or swap" >&2; exit 2; }
JOBS="${JOBS:-100000}"; ONLY="${ONLY:-single_core multi_core}"
CACHE_KB=266240; MEM_KB=2662400; STRIDE=64
mkdir -p workload3/results
declare -A PROFILE_VM=([single_core]=worker6 [multi_core]=worker7) SWAP_VM=([single_core]=worker7 [multi_core]=worker6)
declare -A POD=([single_core]=rq2-single-instance0 [multi_core]=rq2-multi) ENEMY_CPUS=([single_core]=2,3,0 [multi_core]=3,0)
declare -A INSTANCES=([single_core]="instance0" [multi_core]="instance0 instance1")

phase() {   # phase <model> <vm> <out root> <condition[:enemy KB]>...
    model=$1; vm=$2; out=$3; shift 3          # plain variables: phase runs in its own subshell, and the EXIT trap needs them
    ns=rq2-node-prep-$vm; node=rt-k8s-worker-${vm#worker}; log=workload3/results/${model}_${PHASE}.log
    say() { printf '[%s] %s %s\n' "$(date -u +%H:%M:%S)" "$model@$vm" "$*" | tee -a "$log"; }
    agent=$(kubectl -n "$ns" get pod -l app=rq1-agent --field-selector "spec.nodeName=$node" -o jsonpath='{.items[0].metadata.name}')
    [ -n "$agent" ] || { say "FATAL no node-prep agent for $node in $ns"; return 1; }
    host=$(kubectl get node "$node" -o jsonpath='{.metadata.labels.kubernetes\.io/hostname}')
    on_node() { kubectl -n "$ns" exec -i "$agent" -- nsenter --target 1 --mount -- bash -s -- "$@"; }
    stop() { on_node < stress1/campaign_stop_enemies.sh 2>&1 | tee -a "$log" | grep -q STILL_ALIVE && say "FATAL enemy not stopped on $node"; }
    strays() { kubectl -n "$ns" exec "$agent" -- nsenter --target 1 --mount --pid -- pgrep -x rq2-enemy > /dev/null 2>&1; }   # BY NAME: stop only knows its own pidfile
    clean() { if strays; then say "FATAL: an rq2-enemy is running on $node that this script did not start ($1): the data would be contaminated; stop it: kubectl -n $ns exec -i $agent -- nsenter --target 1 --mount --pid -- pkill -x rq2-enemy"; exit 1; fi; }
    trap stop EXIT; trap 'exit 130' INT TERM            # whatever happens, no enemy is left running
    stop                                                  # clean start
    clean "at the start"

    for spec in "$@"; do
        cond=${spec%%:*}; kb=${spec#*:}; [ "$kb" = "$spec" ] && kb=""
        say "=== $cond ($JOBS jobs)"
        clean "before $cond"
        [ -n "$kb" ] && { on_node "$kb" $STRIDE "${ENEMY_CPUS[$model]}" < stress1/campaign_start_enemies.sh 2>&1 | tee -a "$log" | grep -qE "MISSING|LOW_CPU" && { say "FATAL enemy not running"; stop; return 1; }; }
        sed -E -e "s#^([[:space:]]*)nodeSelector:.*#\1nodeSelector: { experiment-model: rq2, kubernetes.io/hostname: $host }#" \
               -e "s#jobs=[0-9]+#jobs=$JOBS#" workload3/pods/${model}_pod.yaml > "workload3/results/.${model}.yaml"
        ok=0
        for try in 1 2; do
            kubectl -n rq2 delete pod "${POD[$model]}" --ignore-not-found > /dev/null 2>&1
            kubectl apply -f "workload3/results/.${model}.yaml" > /dev/null 2>&1 && wait_pod "$((JOBS / 100 + 600))" \
              && OUT_ROOT="$out" NODE_PREP_NS="$ns" AGENT_POD="$agent" TIMEOUT="$((JOBS / 100 + 600))s" workload/pull_results.sh "$model" "$cond" >> "$log" 2>&1 \
              && check "$out/$model/$cond" && { ok=1; break; }
            say "attempt $try failed (pod state and logs are in $log)"; diag
        done
        [ -n "$kb" ] && stop
        clean "after $cond"
        [ $ok = 1 ] && say "$cond done" || { say "$cond FAILED"; echo "$model@$vm $cond" >> workload3/results/failed_$PHASE.txt; }
        sleep 10
    done
}

wait_pod() {   # 0 when the pod Succeeded; 1 when it Failed or <timeout> seconds passed (a failed pod is seen at once, not after the timeout)
    local t=0 phase
    while [ "$t" -lt "$1" ]; do
        phase=$(kubectl -n rq2 get pod "${POD[$model]}" -o jsonpath='{.status.phase}' 2>/dev/null)
        [ "$phase" = Succeeded ] && return 0
        [ "$phase" = Failed ] && return 1
        sleep 5; t=$((t + 5))
    done
    return 1
}

diag() {   # state and logs of the pod, written to the log BEFORE the pod is deleted for the next attempt
    { echo "--- pod ${POD[$model]} at the failure:"; kubectl -n rq2 get pod "${POD[$model]}" -o wide
      kubectl -n rq2 describe pod "${POD[$model]}" | tail -n 12; echo "--- its logs:"; kubectl -n rq2 logs "${POD[$model]}" --tail=15; } >> "$log" 2>&1
}

check() {   # every instance: JOBS rows, FIFO + affinity + mlock really set
    local dir=$1 i
    for i in ${INSTANCES[$model]}; do
        [ "$(( $(wc -l < "$dir/$i.csv") - 1 ))" = "$JOBS" ] && python3 -c "
import json, sys
m = json.load(open(sys.argv[1])); sys.exit(0 if all(m[k] for k in ('mlockall_ok', 'sched_fifo_ok', 'affinity_ok')) else 1)" "$dir/$i.meta.json" || return 1
    done
}

rm -f workload3/results/failed_$PHASE.txt
for model in $ONLY; do                                   # a running (or left over) pod would be deleted by the runs below
    kubectl -n rq2 get pod "${POD[$model]}" > /dev/null 2>&1 && { echo "pod rq2/${POD[$model]} exists (another run, or a leftover): wait for it or: kubectl -n rq2 delete pod ${POD[$model]}" >&2; exit 1; }
done
set -m                                                   # each phase gets its own process group, which the trap below can kill
trap 'trap "" INT TERM; echo "interrupted: stopping the runs and the enemies"; kill -TERM -- $(jobs -p | sed "s/^/-/") 2>/dev/null; wait; exit 130' INT TERM
for model in $ONLY; do
    if [ "$PHASE" = profile ]; then
        ( phase "$model" "${PROFILE_VM[$model]}" workload3/results baseline1 "cache:$CACHE_KB" "memory:$MEM_KB" baseline2 ) &
    else
        vm=${SWAP_VM[$model]}
        ( phase "$model" "$vm" "workload3/alpha_drift/results/$vm" baseline "memory:$MEM_KB" ) &
    fi
done
status=0
for pid in $(jobs -p); do wait "$pid" || status=1; done          # a phase that aborted (FATAL) counts as failed
[ -s workload3/results/failed_$PHASE.txt ] && { echo "FAILED runs:"; cat workload3/results/failed_$PHASE.txt; status=1; }
[ $status = 0 ] && echo "$PHASE: all runs collected" || { echo "$PHASE: NOT complete, see workload3/results/<model>_$PHASE.log"; exit 1; }
