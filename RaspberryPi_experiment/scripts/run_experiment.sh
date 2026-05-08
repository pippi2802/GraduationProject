#!/usr/bin/env bash
# Run the contended periodic workload on the Pi, mirroring the AKS run.
#
# Two processes (procA, procB) each spawn 3 periodic threads. Both processes
# are pinned to the SAME 2 CPUs via taskset so the contention scenario
# matches the 2-vCPU AKS node (Standard_D2ps_v6).
#
# Usage:
#   ./run_experiment.sh [results_dir] [cpu_list]
# Defaults:
#   results_dir = results/<timestamp>
#   cpu_list    = 0,1   (first two CPUs of the Pi)
#
# Outputs (under results_dir):
#   cA_task0.csv ... cA_task2.csv   (procA / 3 threads)
#   cB_task0.csv ... cB_task2.csv   (procB / 3 threads)
#   proc_stat.csv                   (1 Hz /proc/stat sampler)
#   procA.log, procB.log            (stdout of each process)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT_DIR/rt_multi_periodic"
[[ -x "$BIN" ]] || { echo "missing binary; run scripts/build.sh first"; exit 1; }

RESULTS_DIR="${1:-$ROOT_DIR/results/$(date +%Y%m%d-%H%M%S)}"
CPU_LIST="${2:-0,1}"

# Same task spec as ContendedAKS_experiment.
TASK_1="20000:5000:1500"   # T=20ms,  C=5ms
TASK_2="50000:15000:600"   # T=50ms,  C=15ms
TASK_3="100000:25000:300"  # T=100ms, C=25ms

mkdir -p "$RESULTS_DIR"
echo "results dir : $RESULTS_DIR"
echo "cpu pin     : $CPU_LIST"
echo "tasks       : $TASK_1 | $TASK_2 | $TASK_3"

# /proc/stat sampler in the background (host-side, since there is no container).
(
    echo "ts_ns,line"
    while true; do
        ts=$(date +%s%N)
        awk -v ts="$ts" '/^cpu/ {print ts","$0}' /proc/stat
        sleep 1
    done
) > "$RESULTS_DIR/proc_stat.csv" &
SAMPLER_PID=$!
trap 'kill $SAMPLER_PID 2>/dev/null || true' EXIT INT TERM

# Launch both "containers" (just processes here) in parallel, both pinned
# to the same 2 CPUs. The binary aligns its release to a future second
# boundary so both processes start their first invocation at the same instant.
taskset -c "$CPU_LIST" "$BIN" "$RESULTS_DIR" cA \
    "$TASK_1" "$TASK_2" "$TASK_3" > "$RESULTS_DIR/procA.log" 2>&1 &
PA=$!
taskset -c "$CPU_LIST" "$BIN" "$RESULTS_DIR" cB \
    "$TASK_1" "$TASK_2" "$TASK_3" > "$RESULTS_DIR/procB.log" 2>&1 &
PB=$!

echo "procA pid=$PA   procB pid=$PB"
wait $PA $PB

kill $SAMPLER_PID 2>/dev/null || true
wait 2>/dev/null || true

echo "=== done. results in $RESULTS_DIR ==="
ls -1 "$RESULTS_DIR"
