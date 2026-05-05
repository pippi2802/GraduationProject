#!/bin/sh
# Multi-task CFS scenario with 80% CPU utilization
# Output format is the same as periodic_task: task_id iteration time deadline_miss cpu_time relative_deadline

OUTPUT_DIR="cfs_results_80"
mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "CFS Multi-Task 80% Utilization Scenario"
echo "=========================================="
echo ""
echo "System Utilization Breakdown:"
echo "  Task 1: 50ms / 100ms = 50%"
echo "  Task 2: 40ms / 200ms = 20%"
echo "  Task 3: 30ms / 300ms = 10%"
echo "  TOTAL: 80%"
echo ""

# Task 1: High priority, 50% utilization
echo "Task 1: WCET=50ms, Period=100ms, Nice=-10 (50% utilization)"
./periodic_task_cfs -C 50000 -p 100000 -n -10 -N 50 > "$OUTPUT_DIR/task1.txt" &
PID1=$!

# Task 2: Normal priority, 20% utilization  
echo "Task 2: WCET=40ms, Period=200ms, Nice=0 (20% utilization)"
./periodic_task_cfs -C 40000 -p 200000 -n 0 -N 25 > "$OUTPUT_DIR/task2.txt" &
PID2=$!

# Task 3: Low priority, 10% utilization
echo "Task 3: WCET=30ms, Period=300ms, Nice=10 (10% utilization)"
./periodic_task_cfs -C 30000 -p 300000 -n 10 -N 17 > "$OUTPUT_DIR/task3.txt" &
PID3=$!

echo ""
echo "Running tasks... this may take a minute"
wait $PID1 $PID2 $PID3

echo ""
echo "=========================================="
echo "Results saved to $OUTPUT_DIR/"
echo ""

# Show output format
echo "Output Format:"
echo "  task_id | iteration | absolute_time | time_in_period | cpu_time | relative_deadline"
echo ""

if [ -f "$OUTPUT_DIR/task1.txt" ]; then
    echo "Task 1 - First 3 results:"
    head -3 "$OUTPUT_DIR/task1.txt" | grep -v "^#"
fi

echo ""
echo "=========================================="
echo "To analyze results, run:"
echo "  ./analyze_results.sh cfs_results_80"
echo "=========================================="
