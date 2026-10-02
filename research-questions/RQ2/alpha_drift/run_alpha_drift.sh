#!/usr/bin/env bash
# run_alpha_drift.sh <vm-label>      e.g.  run_alpha_drift.sh worker6
#                                          run_alpha_drift.sh worker0
#
# Two baseline runs on the VM you name, one after the other, unattended:
#   1. single_core baseline  (workload/pods/single_core_pod.yaml)
#   2. multi_core  baseline  (workload/pods/multi_core_pod.yaml)
# Run it once per VM to compare VM types. Each run is 100000 jobs (the --jobs
# baked into the pod specs, ~70 min each at period-ms=41.667, so ~2.3 h per
# VM). No stress: both runs are plain baselines, so the script first confirms
# no enemy is running on the node.
#
# <vm-label> is the suffix of that VM's node-prep namespace
# (rq2-node-prep-<vm-label>, override with NODE_PREP_NS). The node the agent
# pod runs on is the node the workload is pinned to: the script writes a copy
# of each pod spec with its nodeSelector replaced by
# { experiment-model: rq2, kubernetes.io/hostname: <that node> }, so either
# model can run on any VM regardless of its rq2-role label. The shared specs
# in workload/pods/ are never edited. The node must carry experiment-model=rq2
# (the script checks, and tells you the command, but never labels nodes).
#
# Run one VM at a time: both VMs would use the same pod names in namespace rq2.
#
# Same automation as workload/run_campaign.sh: it applies the pod, waits for
# it to Succeed, pulls the CSV + meta.json off the node via the node-prep
# agent (workload/pull_results.sh, no SSH), deletes the pod, and logs every
# step. Pod specs are reused unchanged from workload/pods/ so these runs stay
# directly comparable with the four-condition campaign.
#
# Data lands in (git-ignored):
#   alpha_drift/results/<vm>/single_core/baseline/instance0.{csv,meta.json}
#   alpha_drift/results/<vm>/multi_core/baseline/instance{0,1}.{csv,meta.json}
#   alpha_drift/results/<vm>/manifests/<model>.yaml   (exact spec applied)
# Log: alpha_drift/results/<vm>/alpha_drift.log
#
# After each pull the data is CHECKED (row count == jobs + 1, meta.json says
# mlockall/sched_fifo/affinity all ok). A failed deploy/pull/check is retried
# once; if it still fails the run is recorded as FAILED and the script moves
# on to the next one (see the summary at the end).
#
# Run it detached so it survives your terminal closing - it does NOT
# background itself:
#   nohup alpha_drift/run_alpha_drift.sh worker6 > /dev/null 2>&1 &
# or in tmux/screen. Resume after a crash without redoing a finished run:
#   START_FROM=multi_core alpha_drift/run_alpha_drift.sh worker6
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RQ2_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$RQ2_ROOT"

VM="${1:?usage: run_alpha_drift.sh <vm-label>   (e.g. worker6, worker0)}"
[[ "$VM" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] || { echo "bad vm label: $VM" >&2; exit 2; }
NODE_PREP_NS="${NODE_PREP_NS:-rq2-node-prep-$VM}"

OUT_ROOT="$SCRIPT_DIR/results/$VM"
export OUT_ROOT                      # read by workload/pull_results.sh
CONDITION="baseline"
JOBS="${JOBS:-100000}"               # must match --jobs in the pod specs; used only for the row-count check
ATTEMPTS="${ATTEMPTS:-2}"
SETTLE_S="${SETTLE_S:-10}"
START_FROM="${START_FROM:-single_core}"
WORKLOAD_NS="${WORKLOAD_NS:-rq2}"

mkdir -p "$OUT_ROOT"
MANIFEST_DIR="$OUT_ROOT/manifests"
mkdir -p "$MANIFEST_DIR"
LOG="$OUT_ROOT/alpha_drift.log"

log() {
    printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"
}

# Per-model settings (pods/instances as in workload/pull_results.sh). The VM
# comes from the command line, not from the model.
set_model() {
    MODEL="$1"
    case "$MODEL" in
        single_core)
            SRC_YAML="workload/pods/single_core_pod.yaml"
            PODS=(rq2-single-instance0)
            INSTANCES=(instance0)
            ;;
        multi_core)
            SRC_YAML="workload/pods/multi_core_pod.yaml"
            PODS=(rq2-multi)
            INSTANCES=(instance0 instance1)
            ;;
        *)
            echo "unknown model: $MODEL" >&2
            exit 2
            ;;
    esac
}

# Finds the VM's agent and node, checks the node label, and writes the pinned
# copy of the pod spec. Done once per script run.
resolve_vm() {
    export NODE_PREP_NS WORKLOAD_NS    # read by workload/pull_results.sh
    AGENT=$(kubectl -n "$NODE_PREP_NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) || true
    [ -n "$AGENT" ] || { log "FATAL: no node-prep agent in namespace $NODE_PREP_NS - is '$VM' the right label? (set NODE_PREP_NS to override)"; exit 1; }
    NODE_NAME=$(kubectl -n "$NODE_PREP_NS" get pod "$AGENT" -o jsonpath='{.spec.nodeName}')
    HOST_LABEL=$(kubectl get node "$NODE_NAME" -o jsonpath='{.metadata.labels.kubernetes\.io/hostname}')
    [ -n "$NODE_NAME" ] && [ -n "$HOST_LABEL" ] || { log "FATAL: could not resolve the node of agent $AGENT"; exit 1; }
    if [ "$(kubectl get node "$NODE_NAME" -o jsonpath='{.metadata.labels.experiment-model}')" != "rq2" ]; then
        log "FATAL: node $NODE_NAME lacks the label experiment-model=rq2 that the pod specs select on. Label it yourself: kubectl label node $NODE_NAME experiment-model=rq2"
        exit 1
    fi
    log "vm=$VM agent=$AGENT node=$NODE_NAME hostname-label=$HOST_LABEL"
}

# Copy of $SRC_YAML with its (single) nodeSelector pinned to this VM's node.
make_manifest() {
    POD_YAML="$MANIFEST_DIR/$MODEL.yaml"
    sed -E "s#^([[:space:]]*)nodeSelector:.*#\1nodeSelector: { experiment-model: rq2, kubernetes.io/hostname: $HOST_LABEL }#" \
        "$SRC_YAML" > "$POD_YAML"
    if [ "$(grep -c 'kubernetes.io/hostname' "$POD_YAML")" -ne 1 ] || \
       [ "$(grep -c 'nodeSelector' "$SRC_YAML")" -ne 1 ]; then
        log "FATAL: expected exactly one nodeSelector line in $SRC_YAML - not applying a pinned copy I can't vouch for"
        exit 1
    fi
}

# A baseline must not run next to a leftover stress enemy, nor next to an old
# pod of the same name (apply would say "unchanged" and pull_results would
# collect stale data). Both abort the whole script rather than guess.
preflight() {
    local pod enemies
    enemies=$(kubectl -n "$NODE_PREP_NS" exec -i "$AGENT" -- nsenter --target 1 --mount --pid -- \
        bash -c 'pgrep -x rq2-enemy || true' 2>/dev/null) || true
    if [ -n "$enemies" ]; then
        log "FATAL: rq2-enemy still running on $NODE_PREP_NS (pids: $(echo $enemies)) - a baseline would not be clean. Stop it first."
        exit 1
    fi
    for pod in "${PODS[@]}"; do
        if kubectl -n "$WORKLOAD_NS" get pod "$pod" >/dev/null 2>&1; then
            log "FATAL: pod $WORKLOAD_NS/$pod already exists - delete it (kubectl -n $WORKLOAD_NS delete pod $pod) or let it finish, then rerun"
            exit 1
        fi
    done
}

cleanup_stuck_pods() {
    local pod
    for pod in "${PODS[@]}"; do
        kubectl -n "$WORKLOAD_NS" delete pod "$pod" --ignore-not-found 2>&1 | tee -a "$LOG"
    done
}

# Row count and the real-time flags in meta.json. Returns non-zero on any problem.
check_data() {
    local dir="$OUT_ROOT/$MODEL/$CONDITION" inst rows
    for inst in "${INSTANCES[@]}"; do
        rows=$(( $(wc -l < "$dir/$inst.csv") - 1 ))
        if [ "$rows" -ne "$JOBS" ]; then
            log "CHECK FAILED: $dir/$inst.csv has $rows rows, expected $JOBS"
            return 1
        fi
        if ! python3 - "$dir/$inst.meta.json" <<'EOF'
import json, sys
m = json.load(open(sys.argv[1]))
bad = [k for k in ("mlockall_ok", "sched_fifo_ok", "affinity_ok") if m.get(k) is not True]
if bad:
    print("CHECK FAILED: %s not true in %s" % (", ".join(bad), sys.argv[1]))
    sys.exit(1)
EOF
        then
            log "CHECK FAILED: meta.json flags for $inst"
            return 1
        fi
    done
    log "data check OK ($VM/$MODEL/$CONDITION: ${#INSTANCES[@]} instance(s) x $JOBS jobs, rt flags ok)"
}

FAILED=()

run_one() {
    set_model "$1"
    log "=== alpha_drift: $VM $MODEL $CONDITION ($JOBS jobs) ==="
    make_manifest
    preflight

    local attempt ok=0
    for attempt in $(seq 1 "$ATTEMPTS"); do
        if [ "$attempt" -gt 1 ]; then
            log "retrying $MODEL (attempt $attempt/$ATTEMPTS)"
            cleanup_stuck_pods
        fi

        log "deploying pod: $POD_YAML"
        if ! kubectl apply -f "$POD_YAML" 2>&1 | tee -a "$LOG"; then
            log "kubectl apply failed (attempt $attempt/$ATTEMPTS)"
            continue
        fi

        log "waiting for completion and pulling results..."
        if workload/pull_results.sh "$MODEL" "$CONDITION" 2>&1 | tee -a "$LOG" \
            && check_data; then
            ok=1
            break
        fi
        log "pull/check failed for $MODEL (attempt $attempt/$ATTEMPTS)"
    done

    if [ "$ok" != 1 ]; then
        FAILED+=("$MODEL")
        log "=== $MODEL FAILED after $ATTEMPTS attempt(s) - data missing/incomplete, do not trust it ==="
    else
        log "=== $MODEL done ==="
    fi
    log "settling ${SETTLE_S}s before the next step..."
    sleep "$SETTLE_S"
}

resolve_vm
log "alpha_drift start: vm=$VM start_from=$START_FROM jobs=$JOBS out=$OUT_ROOT"

case "$START_FROM" in
    single_core) run_one single_core ;&
    multi_core)  run_one multi_core ;;
    *)
        log "ERROR: unknown START_FROM=$START_FROM (expected single_core or multi_core)"
        exit 2
        ;;
esac

echo | tee -a "$LOG"
if [ ${#FAILED[@]} -eq 0 ]; then
    log "alpha_drift complete on $VM: both baselines collected successfully"
else
    log "alpha_drift on $VM finished with ${#FAILED[@]} FAILED run(s): ${FAILED[*]} - rerun individually with START_FROM"
fi
log "results in $OUT_ROOT/{single_core,multi_core}/$CONDITION/"
