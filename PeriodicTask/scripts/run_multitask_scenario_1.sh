#!/bin/sh
# Multi-task scheduling scenario for deadline analysis
# This script runs multiple periodic tasks in parallel to simulate real scheduling

OUTPUT_DIR="multitask_results_1"
mkdir -p "$OUTPUT_DIR"

echo "=== Multi-Task Scheduling Scenario ==="
echo "Running 3 tasks with different priorities and periods..."
echo ""

# Task 1: High priority, short period (100ms), 50 iterations
echo "Task 1: Period=100ms, WCET=40ms, Priority=1"
./periodic_task -C 40000 -p 100000 -P 1 -N 50 > "$OUTPUT_DIR/task1.txt" &
PID1=$!

# Task 2: Medium priority, medium period (200ms), 25 iterations
echo "Task 2: Period=200ms, WCET=50ms, Priority=2"
./periodic_task -C 50000 -p 200000 -P 2 -N 30 > "$OUTPUT_DIR/task2.txt" &
PID2=$!

# Task 3: Low priority, long period (300ms), 17 iterations
echo "Task 3: Period=300ms, WCET=20ms, Priority=3"
./periodic_task -C 20000 -p 300000 -P 3 -N 30 > "$OUTPUT_DIR/task3.txt" &
PID3=$!

echo "Waiting for all tasks to complete..."
wait $PID1 $PID2 $PID3

echo ""
echo "=== Results saved to $OUTPUT_DIR/ ==="
echo ""
echo "Task 1 Results:"
head -5 "$OUTPUT_DIR/task1.txt"
echo ""
echo "Task 2 Results:"
head -5 "$OUTPUT_DIR/task2.txt"
echo ""
echo "Task 3 Results:"
head -5 "$OUTPUT_DIR/task3.txt"
echo ""
echo "Output format: task_id iteration deadline_miss_time CPU_time relative_deadline"
