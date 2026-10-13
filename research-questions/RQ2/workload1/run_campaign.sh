#!/usr/bin/env bash
# run_campaign.sh <single_core|multi_core>
#
# Runs baseline1 -> cache -> memory -> baseline2 back to back, unattended,
# at whatever --jobs is baked into the pod's own YAML/config (100000 by
# default - each condition takes ~70 minutes at period-ms=41.667, so the
# whole thing takes several hours). Logs every step to
# results/<model>_campaign.log so you can check progress without watching
# the terminal.
#
# Never trusts that a signal/delete actually took effect - every state
# change is POLLED and CONFIRMED before moving on (same principle as
# RQ1's run_job.sh: wait_manifest_gone/wait_cpu_free/confirm_burning_cpu).
# In particular: stopping an enemy blocks until its pid is actually gone
# (escalating to SIGKILL if it won't die), so cache-enemy interference can
# never bleed into the memory condition that follows it.
#
# A pod-deploy/collect failure is retried once; if a condition still fails
# after that, it's recorded and the campaign moves on to the next
# condition rather than getting stuck - see the FAILED summary at the end.
# An enemy that won't confirm stopped is NOT survivable (data after that
# point can't be trusted) and aborts the whole script immediately.
#
# Run this detached so it survives your terminal closing - it does NOT
# background itself:
#   nohup workload/run_campaign.sh single_core > /dev/null 2>&1 &
# or in tmux/screen. Another workload: POD_YAML=<its pod yaml> OUT_ROOT=<its results folder> (AGENT_POD / NODE_PREP_NS pick the node's agent). single_core (worker6) and multi_core (worker7) are on
# different nodes, so you can run both scripts at once to halve the wait.
set -euo pipefail

MODEL="${1:?usage: run_campaign.sh <single_core|multi_core>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RQ2_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$RQ2_ROOT"

CACHE_SIZE_KB="${CACHE_SIZE_KB:-266240}"
MEMORY_SIZE_KB="${MEMORY_SIZE_KB:-2662400}"
STRIDE_BYTES="${STRIDE_BYTES:-64}"
CONDITION_ATTEMPTS="${CONDITION_ATTEMPTS:-2}"
SETTLE_S="${SETTLE_S:-10}"
# Resume after a crash without redoing already-collected conditions, e.g.
# after baseline1 succeeded but the script died before cache:
#   START_FROM=cache workload/run_campaign.sh multi_core
START_FROM="${START_FROM:-baseline1}"

case "$MODEL" in
    single_core)
        POD_YAML="${POD_YAML:-workload/pods/single_core_pod.yaml}"
        NODE_PREP_NS="${NODE_PREP_NS:-rq2-node-prep-worker6}"
        ENEMY_CPUS="${ENEMY_CPUS:-2,3,0}"   # dial 3: all free RT cores + housekeeping
        CLEANUP_PODS=(rq2-single-instance0)
        ;;
    multi_core)
        POD_YAML="${POD_YAML:-workload/pods/multi_core_pod.yaml}"
        NODE_PREP_NS="${NODE_PREP_NS:-rq2-node-prep-worker7}"
        ENEMY_CPUS="${ENEMY_CPUS:-3,0}"      # dial 2: the only free cores (cpu1,2 are the workload)
        CLEANUP_PODS=(rq2-multi)
        ;;
    *)
        echo "unknown model: $MODEL (expected single_core or multi_core)" >&2
        exit 2
        ;;
esac

mkdir -p results
LOG="results/${MODEL}_campaign.log"

log() {
    printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"
}

AGENT="${AGENT_POD:-$(kubectl -n "$NODE_PREP_NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}')}"
[ -n "$AGENT" ] || { log "ERROR: no node-prep agent found in $NODE_PREP_NS"; exit 1; }

FAILED_CONDITIONS=()

# Starts each enemy, then CONFIRMS it's genuinely burning cpu (not just
# started-then-stuck/crashed) - aborts the whole campaign if any enemy
# doesn't check out, rather than silently collecting data against a
# nonfunctional stressor.
start_enemies() {
    local size_kb="$1" result
    log "starting enemies (size=${size_kb}KB, stride=${STRIDE_BYTES}) on cpus $ENEMY_CPUS"
    result=$(kubectl -n "$NODE_PREP_NS" exec -i "$AGENT" -- nsenter --target 1 --mount -- \
        bash -s -- "$size_kb" "$STRIDE_BYTES" "$ENEMY_CPUS" < stress/campaign_start_enemies.sh 2>&1) || true
    echo "$result" | tee -a "$LOG"
    if echo "$result" | grep -qE "MISSING|LOW_CPU"; then
        log "FATAL: an enemy failed to start or isn't genuinely running - aborting rather than trust this condition"
        exit 1
    fi
}

# Sends SIGTERM, then POLLS until every pid is actually gone (escalating to
# SIGKILL after a grace period) before returning. This is the fix for the
# thing that actually matters: a still-dying cache enemy must never still
# be running by the time the memory condition's start_enemies begins.
stop_enemies() {
    log "stopping enemies"
    local result
    result=$(kubectl -n "$NODE_PREP_NS" exec -i "$AGENT" -- nsenter --target 1 --mount -- \
        bash -s -- < stress/campaign_stop_enemies.sh 2>&1) || true
    echo "$result" | tee -a "$LOG"
    if echo "$result" | grep -q "STILL_ALIVE_AFTER_SIGKILL"; then
        log "FATAL: could not confirm enemies stopped even after SIGKILL - aborting to avoid contaminating the next condition"
        exit 1
    fi
}

cleanup_stuck_pods() {
    local pod
    for pod in "${CLEANUP_PODS[@]}"; do
        kubectl -n rq2 delete pod "$pod" --ignore-not-found 2>&1 | tee -a "$LOG"
    done
}

run_condition() {
    local condition="$1" enemy_size_kb="${2:-}"
    log "=== condition: $condition (model=$MODEL) ==="
    [ -n "$enemy_size_kb" ] && start_enemies "$enemy_size_kb"

    local attempt ok=0
    for attempt in $(seq 1 "$CONDITION_ATTEMPTS"); do
        [ "$attempt" -gt 1 ] && { log "retrying $condition (attempt $attempt/$CONDITION_ATTEMPTS)"; cleanup_stuck_pods; }

        log "deploying pod: $POD_YAML"
        if ! kubectl apply -f "$POD_YAML" 2>&1 | tee -a "$LOG"; then
            log "kubectl apply failed (attempt $attempt/$CONDITION_ATTEMPTS)"
            continue
        fi

        log "waiting for completion and pulling results..."
        if workload/pull_results.sh "$MODEL" "$condition" 2>&1 | tee -a "$LOG"; then
            ok=1
            break
        fi
        log "pull_results.sh failed for $condition (attempt $attempt/$CONDITION_ATTEMPTS)"
    done

    [ -n "$enemy_size_kb" ] && stop_enemies

    if [ "$ok" != 1 ]; then
        FAILED_CONDITIONS+=("$condition")
        log "=== $condition FAILED after $CONDITION_ATTEMPTS attempt(s) - data for this condition is missing/incomplete, do not trust it ==="
    else
        log "=== $condition done ==="
    fi

    log "settling ${SETTLE_S}s before the next condition..."
    sleep "$SETTLE_S"
}

log "campaign start: model=$MODEL enemy_cpus=$ENEMY_CPUS cache=${CACHE_SIZE_KB}KB memory=${MEMORY_SIZE_KB}KB start_from=$START_FROM"

case "$START_FROM" in
    baseline1) run_condition baseline1 ;&
    cache)     run_condition cache "$CACHE_SIZE_KB" ;&
    memory)    run_condition memory "$MEMORY_SIZE_KB" ;&
    baseline2) run_condition baseline2 ;;
    *)
        log "ERROR: unknown START_FROM=$START_FROM (expected baseline1, cache, memory, or baseline2)"
        exit 2
        ;;
esac

echo | tee -a "$LOG"
if [ ${#FAILED_CONDITIONS[@]} -eq 0 ]; then
    log "campaign complete: all 4 conditions collected successfully"
else
    log "campaign finished with ${#FAILED_CONDITIONS[@]} FAILED condition(s): ${FAILED_CONDITIONS[*]} - do not trust these, rerun them individually"
fi
log "results in results/$MODEL/{baseline1,cache,memory,baseline2}/"
