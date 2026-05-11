#!/usr/bin/env bash
# Driver: render manifest, deploy pod onto the Raspberry Pi worker, wait
# for both containers to finish, copy CSV results out, then delete the pod.
#
# Mirrors ContendedAKS_experiment/scripts/run_experiment.sh.
#
# Usage:
#   ./run_experiment.sh <IMAGE> <NODE_NAME> [results_dir]
#
# Example (single-node k3s on the Pi, image imported locally as
# `rt-contended-pi:0.1`):
#   ./run_experiment.sh rt-contended-pi:0.1 raspberrypi
#
# Produces (under results_dir):
#   cA_task0.csv ... cA_task2.csv   (procA / 3 threads)
#   cB_task0.csv ... cB_task2.csv   (procB / 3 threads)
#   cA_proc_stat.csv  cB_proc_stat.csv

set -euo pipefail

IMAGE="${1:?image ref required (e.g. rt-contended-pi:0.1 or <registry>/rt-contended-pi:0.1)}"
NODE_NAME="${2:?node name required (kubectl get nodes -- the Pi hostname)}"
RESULTS_DIR="${3:-results/$(date +%Y%m%d-%H%M%S)}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$RESULTS_DIR"

POD="rt-contended"
MANIFEST="$ROOT_DIR/k8s/workload-contended.yaml"

render() {
    # `|` not safe in image refs; both placeholders use plain text only.
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
for f in cA_task0.csv cA_task1.csv cA_task2.csv \
         cB_task0.csv cB_task1.csv cB_task2.csv \
         cA_proc_stat.csv cB_proc_stat.csv; do
    kubectl cp "$POD:/out/$f" "$RESULTS_DIR/$f" -c rt-a || \
        echo "WARN: missing $f"
done

echo "Results in: $RESULTS_DIR"
