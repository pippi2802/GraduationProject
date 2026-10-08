#!/usr/bin/env bash
# run_experiments.sh <profile|swap>      (detach it: nohup workload2/run_experiments.sh profile > workload2/results/profile.out 2>&1 &)
#
# The segmentation workload, period 100 ms, through the generic scripts of the procedure (step 2 and step 3), so that step 4 finds the data without any path.
#
# profile : baseline1, cache, memory, baseline2 of each scenario on its node, 50000 jobs per run
#           -> procedure/step2_profiling/results/<scenario>/{baseline1,cache,memory,baseline2}/        (about 5.7 h, both scenarios at the same time)
# swap    : the other node of each scenario: one baseline (label "swap"), then one stressed run paired with it, 30000 jobs per run
#           -> procedure/step3_drift_runs/results/<scenario>/{extra_baselines/swap,stress_run}/        (about 1.75 h)
# Scenarios: seg_single (profile on worker6, swap on worker7) and seg_multi (profile on worker7, swap on worker6): in each phase the two run at the same time
# on different nodes. The two phases are independent: run one, work on its data, run the other later; never both at once (same pod names, same nodes).
# Then, in procedure/step4_parameter_derivation:  python3 main.py --scenarios seg_single seg_multi
#
#   DRY_RUN=1 workload2/run_experiments.sh profile              prints the plan and touches nothing
#   ONLY=seg_single workload2/run_experiments.sh swap            one scenario;   JOBS_PROFILE=50000 JOBS_SWAP=30000 change the job counts
#   tail -f workload2/results/seg_single_profile.log             progress (also seg_multi_*.log, and the swap logs): the screen only gets the summary
#   pkill -TERM -f "[w]orkload2/run_experiments.sh"              stop it (Ctrl-C also works): the runs, the pods and the enemies are stopped
#
# The scripts below do the work: pin the pod to the node, start/stop the enemies (confirmed, and checked by name for strays), wait for the pod (a failed pod is seen at
# once), pull and check the CSVs (exactly the job count, FIFO/affinity/mlock flags true), retry a failed run once. Additionally, before the first run on a node
# this script checks the node's kubepods-besteffort.slice: it must hold the period of these pods (100000 us); another workload's period makes a two-core pod fail with
# StartError, so a slice with another period is reset (runtime 0, then the period) while no pod runs. --no-slice-reset leaves it alone.
# Prerequisites: kubectl, python3, the node-prep agents, the enemy installed on both nodes (procedure/step2_profiling/install_enemy.sh), image pippina2/rq2-seg:v2 pushed.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RQ2="$(dirname "$HERE")"
STEP2="$RQ2/procedure/step2_profiling/run_profiling.sh"; STEP3="$RQ2/procedure/step3_drift_runs/run_extra.sh"
PHASE="${1:-}"; shift || true
[[ "$PHASE" =~ ^(profile|swap)$ ]] || { sed -n '2,/^set /p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'; exit 2; }
SLICE_RESET=1; for a in "$@"; do [ "$a" = --no-slice-reset ] && SLICE_RESET=0; done
JOBS_PROFILE="${JOBS_PROFILE:-50000}" JOBS_SWAP="${JOBS_SWAP:-30000}" ONLY="${ONLY:-seg_single seg_multi}" DRY_RUN="${DRY_RUN:-0}"
PERIOD_US=100000                                  # the claim period of workload2/pods/*.yaml
mkdir -p "$HERE/results"

# scenario -> pod yaml, instances, enemy cpus, results dir and prefix on the node; the profiling node and the swap node
declare -A POD=([seg_single]=single_core_pod.yaml [seg_multi]=multi_core_pod.yaml) INST=([seg_single]=1 [seg_multi]=2)
declare -A ENEMY=([seg_single]=2,3,0 [seg_multi]=3,0) NAME=([seg_single]=single_core [seg_multi]=multi_core)
declare -A PROFILE_NODE=([seg_single]=6 [seg_multi]=7) SWAP_NODE=([seg_single]=7 [seg_multi]=6)

common() {   # <scenario> <worker number>: the arguments the step scripts share
    local sc=$1 w=$2
    echo --scenario "$sc" --pod-yaml "$HERE/pods/${POD[$sc]}" --node "rt-k8s-worker-$w" --agent-ns "rq2-node-prep-worker$w" \
         --node-dir "/var/lib/rq2/results/${NAME[$sc]}" --prefix "${NAME[$sc]}" --instances "${INST[$sc]}"
}

slice_check() {   # <worker number> <log>: the slice must hold this workload's period
    local w=$1 ns agent out
    ns="rq2-node-prep-worker$w"
    agent=$(kubectl -n "$ns" get pod -l app=rq1-agent --field-selector "spec.nodeName=rt-k8s-worker-$w" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    [ -n "$agent" ] || { echo "no node-prep agent on rt-k8s-worker-$w in $ns" >&2; return 1; }
    out=$(kubectl -n "$ns" exec -i "$agent" -- nsenter --target 1 --mount --pid -- bash -s -- "$PERIOD_US" <<'EOS' 2>&1 | tr '\n' ' '
d=/sys/fs/cgroup/kubepods.slice/kubepods-besteffort.slice
now=$(cat $d/cpu.rt_period_us)
echo "period $now runtime $(cat $d/cpu.rt_runtime_us)"
if [ "$now" != "$1" ]; then
    if echo 0 > $d/cpu.rt_runtime_us && echo "$1" > $d/cpu.rt_period_us; then echo "-> reset to period $(cat $d/cpu.rt_period_us)"; else echo "RESET FAILED"; fi
fi
EOS
)
    echo "node slice on worker$w: $out" >> "$2"
    [[ "$out" != *"RESET FAILED"* ]]
}

step() {   # <log> <command...>: runs one step script with its output appended to the log; TERM/INT of this worker are forwarded to it, and it is waited for
    local log=$1 rc; shift
    "$@" >> "$log" 2>&1 &
    CHILD=$!
    wait "$CHILD"; rc=$?
    while kill -0 "$CHILD" 2>/dev/null; do wait "$CHILD"; rc=$?; done      # a trapped signal ends the first wait early: wait for the step script to finish its own clean-up
    CHILD=""
    return "$rc"
}

run_scenario() {   # <scenario>: one scenario's phase, sequential; runs in its own subshell (a worker)
    local sc=$1 log="$HERE/results/${1}_$PHASE.log" w args
    CHILD=""
    trap '[ -n "$CHILD" ] && kill -TERM "$CHILD" 2>/dev/null; STOPPED=1' INT TERM      # a signal to this worker (pkill matches it too) is passed on to the step script
    STOPPED=0
    if [ "$PHASE" = profile ]; then
        w=${PROFILE_NODE[$sc]}; args=$(common "$sc" "$w")
        [ "$DRY_RUN" = 1 ] && { echo "[$sc] would run: $STEP2 $args --enemy-cpus ${ENEMY[$sc]} --jobs $JOBS_PROFILE"; return 0; }
        [ "$SLICE_RESET" = 1 ] && { slice_check "$w" "$log" || return 1; }
        # shellcheck disable=SC2086
        step "$log" "$STEP2" $args --enemy-cpus "${ENEMY[$sc]}" --jobs "$JOBS_PROFILE"
        return $?
    fi
    w=${SWAP_NODE[$sc]}; args=$(common "$sc" "$w")
    if [ "$DRY_RUN" = 1 ]; then
        echo "[$sc] would run: $STEP3 baseline --label swap $args --jobs $JOBS_SWAP"
        echo "[$sc] then:      $STEP3 stress --paired-with swap $args --enemy-cpus ${ENEMY[$sc]} --jobs $JOBS_SWAP"; return 0
    fi
    [ "$SLICE_RESET" = 1 ] && { slice_check "$w" "$log" || return 1; }
    # shellcheck disable=SC2086
    step "$log" "$STEP3" baseline --label swap $args --jobs "$JOBS_SWAP" || { echo "[$sc] the baseline failed (or was stopped): the stressed run, which is paired with it, is not started" >> "$log"; return 1; }
    [ "$STOPPED" = 1 ] && return 130
    step "$log" "$STEP3" stress --paired-with swap $args --enemy-cpus "${ENEMY[$sc]}" --jobs "$JOBS_SWAP"
    return $?
}

if [ "$DRY_RUN" != 1 ]; then      # a running (or left over) pod would be deleted by the runs
    for sc in $ONLY; do
        pod=$(grep -m1 -oE 'name: "rq2-(single-instance0|multi)"$' "$HERE/pods/${POD[$sc]}" | cut -d'"' -f2)
        kubectl -n rq2 get pod "$pod" > /dev/null 2>&1 && { echo "pod rq2/$pod exists (another run, or a leftover): wait for it or: kubectl -n rq2 delete pod $pod" >&2; exit 1; }
    done
fi
WORKERS=()
trap 'trap "" INT TERM; echo "interrupted: stopping the runs and the enemies (the step scripts clean up first)"; kill -TERM "${WORKERS[@]}" 2>/dev/null
      for p in "${WORKERS[@]}"; do for _ in $(seq 180); do kill -0 "$p" 2>/dev/null || break; sleep 1; done; done; exit 130' INT TERM
for sc in $ONLY; do ( run_scenario "$sc" ) & WORKERS+=($!); done
status=0
for pid in "${WORKERS[@]}"; do wait "$pid" || status=1; done          # a worker that failed or aborted (FATAL) counts as failed
[ "$DRY_RUN" = 1 ] && { echo "dry run: nothing was executed"; exit 0; }
[ $status = 0 ] && echo "$PHASE: all runs collected" || { echo "$PHASE: NOT complete, see workload2/results/<scenario>_$PHASE.log"; exit 1; }
