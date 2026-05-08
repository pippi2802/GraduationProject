#!/usr/bin/env bash
# Driver: render manifest, deploy pod, wait for the workload to finish in
# both containers, copy CSV results out to the host, then delete the pod.
#
# Usage:
#   ./run_experiment.sh <IMAGE> <NODE_NAME> [results_dir]
#
# Produces:
#   <results_dir>/cA_task0.csv ... cA_task2.csv
#   <results_dir>/cB_task0.csv ... cB_task2.csv
#   <results_dir>/cA_proc_stat.csv  cB_proc_stat.csv

set -euo pipefail

IMAGE="${1:?image ref required (e.g. <acr>.azurecr.io/rt-contended:0.1)}"
NODE_NAME="${2:?node name required (kubectl get nodes)}"
RESULTS_DIR="${3:-results/$(date +%Y%m%d-%H%M%S)}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$RESULTS_DIR"

POD="rt-contended"
MANIFEST="$ROOT_DIR/k8s/workload-contended.yaml"

render() {
    sed -e "s|IMAGE|$IMAGE|g" -e "s|NODE_NAME|$NODE_NAME|g" "$1"
}

cleanup() {
    echo "Cleaning up pod $POD ..."
    render "$MANIFEST" | kubectl delete -f - --ignore-not-found --wait=false || true
}
trap cleanup EXIT

echo "=== Deploying $POD on $NODE_NAME (image=$IMAGE) ==="
render "$MANIFEST" | kubectl apply -f -

echo "Waiting for pod to be Ready..."
kubectl wait --for=condition=Ready "pod/$POD" --timeout=180s

# Both containers print "[<prefix>] done." after their workload finishes.
# We poll their logs and wait until both have completed.
wait_done() {
    local container="$1" prefix="$2"
    echo "Waiting for $container ($prefix) to finish..."
    while :; do
        if kubectl logs "$POD" -c "$container" 2>/dev/null \
            | grep -q "^\[$prefix\] done"; then
            echo "  -> $container finished."
            return 0
        fi
        sleep 5
    done
}
wait_done rt-a cA
wait_done rt-b cB

echo "=== Copying results to $RESULTS_DIR ==="
# Both containers mount the same emptyDir at /out, so any container works.
for f in cA_task0.csv cA_task1.csv cA_task2.csv \
         cB_task0.csv cB_task1.csv cB_task2.csv \
         cA_proc_stat.csv cB_proc_stat.csv; do
    kubectl cp "$POD:/out/$f" "$RESULTS_DIR/$f" -c rt-a || \
        echo "WARN: missing $f"
done

echo "Results in: $RESULTS_DIR"
