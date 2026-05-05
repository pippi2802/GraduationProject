#!/usr/bin/env bash
# End-to-end driver for the preliminary evaluation.
# Prereqs: kubectl context pointing at the AKS cluster, image already pushed.
#
# Usage:
#   ./run_experiment.sh <IMAGE> <NODE_NAME> [results_dir]
#
# Produces:
#   <results_dir>/solo/{rt_periodic.csv,proc_stat.csv}
#   <results_dir>/noisy/{rt_periodic.csv,proc_stat.csv}

set -euo pipefail

IMAGE="${1:?image ref required}"
NODE_NAME="${2:?node name required}"
RESULTS_DIR="${3:-results/$(date +%Y%m%d-%H%M%S)}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$RESULTS_DIR/solo" "$RESULTS_DIR/noisy"

render() {
    sed -e "s|IMAGE|$IMAGE|g" -e "s|NODE_NAME|$NODE_NAME|g" "$1"
}

run_condition() {
    local name="$1" manifest="$2" pod="$3"
    echo "=== Condition: $name ==="
    render "$manifest" | kubectl apply -f -
    echo "Waiting for $pod to complete..."
    # Wait for the rt-periodic pod to finish.
    kubectl wait --for=condition=Ready "pod/$pod" --timeout=120s || true
    # Poll until Succeeded/Failed.
    while :; do
        phase=$(kubectl get pod "$pod" -o jsonpath='{.status.phase}')
        case "$phase" in
            Succeeded|Failed) break ;;
        esac
        sleep 5
    done
    kubectl cp "$pod:/out/rt_periodic.csv" "$RESULTS_DIR/$name/rt_periodic.csv"
    kubectl cp "$pod:/out/proc_stat.csv"   "$RESULTS_DIR/$name/proc_stat.csv"
    render "$manifest" | kubectl delete -f - --ignore-not-found
}

run_condition solo  "$ROOT_DIR/k8s/workload-solo.yaml"  rt-periodic-solo
run_condition noisy "$ROOT_DIR/k8s/workload-noisy.yaml" rt-periodic-noisy

echo "Results in: $RESULTS_DIR"
