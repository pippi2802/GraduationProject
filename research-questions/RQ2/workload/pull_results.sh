#!/usr/bin/env bash
# pull_results.sh <single_core|multi_core> <condition>
#
# Waits for that model's pod(s) (workload/pods/*_pod.yaml) to finish, pulls
# their CSV + meta.json off the node's hostPath (via the node-prep agent -
# no SSH needed), and drops them into
#     results/<model>/<condition>/<instance>.csv
#     results/<model>/<condition>/<instance>.meta.json
# then deletes the pod(s) so the next condition can be deployed under the
# same pod name.
#
# Assumes you've already `kubectl apply -f workload/pods/<model>_pod.yaml`
# (and started/stopped any stress for this condition around that) - this
# script only waits, collects, and cleans up.
#
# Example sequence for one condition:
#   kubectl apply -f workload/pods/single_core_pod.yaml
#   workload/pull_results.sh single_core baseline1
#   kubectl apply -f workload/pods/single_core_pod.yaml
#   # (start cache enemy, wait, ...)
#   workload/pull_results.sh single_core cache
set -euo pipefail

MODEL="${1:?usage: pull_results.sh <single_core|multi_core> <condition>}"
CONDITION="${2:?usage: pull_results.sh <single_core|multi_core> <condition>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RQ2_ROOT="$(dirname "$SCRIPT_DIR")"
OUT_DIR="$RQ2_ROOT/results/$MODEL/$CONDITION"
WORKLOAD_NS="${WORKLOAD_NS:-rq2}"
# 100000 jobs @ period-ms=41.667 ~= 69.4 min; 5400s (90min) gives real margin.
TIMEOUT="${TIMEOUT:-5400s}"

# PODS: what to wait for. INSTANCES: what result files to pull. These
# differ for multi_core - ONE pod (launch.py spawns 2 subprocesses inside
# it) still produces TWO instances' worth of output files.
case "$MODEL" in
    single_core)
        PODS=(rq2-single-instance0)
        INSTANCES=(instance0)
        NODE_PREP_NS="${NODE_PREP_NS:-rq2-node-prep-worker6}"
        ;;
    multi_core)
        PODS=(rq2-multi)
        INSTANCES=(instance0 instance1)
        NODE_PREP_NS="${NODE_PREP_NS:-rq2-node-prep-worker7}"
        ;;
    *)
        echo "unknown model: $MODEL (expected single_core or multi_core)" >&2
        exit 2
        ;;
esac

AGENT=$(kubectl -n "$NODE_PREP_NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}')
[ -n "$AGENT" ] || { echo "no node-prep agent found in namespace $NODE_PREP_NS" >&2; exit 1; }

for POD in "${PODS[@]}"; do
    echo "[pull_results] waiting for $WORKLOAD_NS/$POD to Succeed (timeout $TIMEOUT)..."
    kubectl -n "$WORKLOAD_NS" wait --for=jsonpath='{.status.phase}'=Succeeded "pod/$POD" --timeout="$TIMEOUT"
done

mkdir -p "$OUT_DIR"
for INSTANCE in "${INSTANCES[@]}"; do
    HOST_BASE="${MODEL}_${INSTANCE}"
    for EXT in csv meta.json; do
        SRC="/var/lib/rq2/results/$MODEL/${HOST_BASE}.${EXT}"
        DST="$OUT_DIR/${INSTANCE}.${EXT}"
        echo "[pull_results] $SRC -> $DST"
        kubectl -n "$NODE_PREP_NS" exec -i "$AGENT" -- nsenter --target 1 --mount -- cat "$SRC" > "$DST"
    done
done

echo "[pull_results] deleting pod(s): ${PODS[*]}"
kubectl -n "$WORKLOAD_NS" delete pod "${PODS[@]}" --ignore-not-found

echo "[pull_results] done: $OUT_DIR"
ls -la "$OUT_DIR"
