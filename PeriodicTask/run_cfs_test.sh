#!/bin/sh
# Scenario: CFS Scheduler with Single Core Contention
# Demonstrates that CFS FAILS to meet real-time deadlines

OUTPUT_DIR="results_cfs"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "SCENARIO 1: CFS Scheduler (SCHED_OTHER)"
echo "=========================================="
echo ""
echo "Task Configuration (single core contention):"
echo "  Task 1: WCET=50ms, Period=100ms, Nice=-10"
echo "  Task 2: WCET=40ms, Period=200ms, Nice=0"
echo "  Task 3: WCET=30ms, Period=300ms, Nice=10"
echo "  Total Utilization: 80%"
echo ""
echo "All tasks pinned to CPU core 0 (single core)"
echo "Expected: Deadline misses due to fair scheduling"
echo ""

# Task 1: CFS with nice -10
taskset -c 0 ./periodic_task_cfs -C 50000 -p 100000 -n -10 -N 50 > "$OUTPUT_DIR/task1.txt" &
PID1=$!

# Task 2: CFS with nice 0
taskset -c 0 ./periodic_task_cfs -C 40000 -p 200000 -n -10 -N 50 > "$OUTPUT_DIR/task2.txt" &
PID2=$!

# Task 3: CFS with nice 10
taskset -c 0 ./periodic_task_cfs -C 30000 -p 300000 -n -10 -N 50 > "$OUTPUT_DIR/task3.txt" &
PID3=$!

echo "Running CFS tasks (this may take a minute)..."
wait $PID1 $PID2 $PID3

echo ""
echo "CFS Results:"
echo "============"

for f in "$OUTPUT_DIR"/task*.txt; do
    if [ -f "$f" ]; then
        task=$(basename "$f" .txt)
        misses=$(grep -v "^#" "$f" | awk '$6>0 {count++} END {print count+0}')
        total=$(grep -v "^#" "$f" | wc -l)
        if [ "$total" -gt 0 ]; then
            pct=$((misses * 100 / total))
            echo "$task: $misses/$total deadline misses ($pct%)"
        fi
    fi
done

echo ""
echo "Results saved to: $OUTPUT_DIR/"
