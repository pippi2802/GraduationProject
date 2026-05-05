#!/bin/sh
# Scenario: SCHED_FIFO Scheduler with Single Core Contention
# Demonstrates that SCHED_FIFO SUCCEEDS in meeting deadlines

OUTPUT_DIR="results_fifo"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "SCENARIO 2: SCHED_FIFO Scheduler (Real-Time)"
echo "=========================================="
echo ""
echo "Task Configuration (single core contention):"
echo "  Task 1: WCET=50ms, Period=100ms, Priority=1 (HIGHEST)"
echo "  Task 2: WCET=40ms, Period=200ms, Priority=2 (MEDIUM)"
echo "  Task 3: WCET=30ms, Period=300ms, Priority=3 (LOWEST)"
echo "  Total Utilization: 80%"
echo ""
echo "All tasks pinned to CPU core 0 (single core)"
echo "Expected: Fewer/no deadline misses with priority-based preemption"
echo ""

# Task 1: SCHED_FIFO priority 1 (highest)
taskset -c 0 ./periodic_task -C 50000 -p 100000 -P 1 -N 50 > "$OUTPUT_DIR/task1.txt" 2>/dev/null &
PID1=$!

# Task 2: SCHED_FIFO priority 2 (medium)
taskset -c 0 ./periodic_task -C 40000 -p 200000 -P 2 -N 25 > "$OUTPUT_DIR/task2.txt" 2>/dev/null &
PID2=$!

# Task 3: SCHED_FIFO priority 3 (lowest)
taskset -c 0 ./periodic_task -C 30000 -p 300000 -P 3 -N 17 > "$OUTPUT_DIR/task3.txt" 2>/dev/null &
PID3=$!

echo "Running SCHED_FIFO tasks (this may take a minute)..."
wait $PID1 $PID2 $PID3

echo ""
echo "SCHED_FIFO Results:"
echo "==================="

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
