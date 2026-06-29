#!/bin/bash
# Comparison analyzer - Shows side-by-side results

echo "=========================================="
echo "SCHEDULER COMPARISON ANALYSIS"
echo "=========================================="
echo ""

analyze_dir() {
    local dir=$1
    local label=$2
    
    echo "[$label]"
    echo ""
    
    for f in "$dir"/task*.txt; do
        if [ -f "$f" ]; then
            task=$(basename "$f" .txt)
            
            # Get configuration
            wcet=$(grep "^#WCET\|^#Fixed C" "$f" | head -1 | awk '{print $NF}')
            period=$(grep "^#Period\|^#T " "$f" | head -1 | awk '{print $NF}')
            
            # Count misses
            misses=$(grep -v "^#" "$f" | awk '$6>0 {count++} END {print count+0}')
            total=$(grep -v "^#" "$f" | wc -l)
            
            if [ "$total" -gt 0 ]; then
                pct=$((misses * 100 / total))
                
                # CPU utilization
                util=$((wcet * 100 / period))
                
                printf "  %-8s: WCET=%5sμs, Period=%7sμs, Util=%3d%%, Misses=%2d/%2d (%3d%%)\n" \
                    "$task" "$wcet" "$period" "$util" "$misses" "$total" "$pct"
            fi
        fi
    done
    echo ""
}

echo "BEFORE YOU BEGIN, MAKE SURE TO RUN:"
echo "  ./run_cfs_test.sh"
echo "  ./run_fifo_test.sh"
echo ""
echo "=========================================="
echo ""

if [ -d "results_cfs" ]; then
    analyze_dir "results_cfs" "CFS (Fair Scheduling)"
else
    echo "[CFS] - Run ./run_cfs_test.sh first"
    echo ""
fi

if [ -d "results_fifo" ]; then
    analyze_dir "results_fifo" "SCHED_FIFO (Real-Time)"
else
    echo "[SCHED_FIFO] - Run ./run_fifo_test.sh first"
    echo ""
fi

echo "=========================================="
echo "INTERPRETATION:"
echo "=========================================="
echo ""
echo "Key Metrics:"
echo "  - Util = WCET/Period (%)    : How much CPU a task needs"
echo "  - Misses                     : Number of deadline violations"
echo "  - Miss %                     : Percentage of missed deadlines"
echo ""
echo "What to expect:"
echo ""
echo "CFS Results:"
echo "  ✗ Task 1 (high nice):   Few misses (gets more CPU time)"
echo "  ⚠ Task 2 (normal):      Some misses (fair sharing)"
echo "  ✗ Task 3 (low nice):    Many misses (least CPU time)"
echo ""
echo "SCHED_FIFO Results:"
echo "  ✓ Task 1 (priority 1):  No/few misses (preempts all)"
echo "  ⚠ Task 2 (priority 2):  Some misses (blocked by Task 1)"
echo "  ✗ Task 3 (priority 3):  Many misses (blocked by 1 and 2)"
echo ""
echo "Conclusion:"
echo "  CFS = Fair but NOT real-time safe"
echo "  FIFO = Real-time safe but not optimal for periodic tasks"
echo "  DEADLINE = Optimal real-time (EDF scheduling)"
echo ""
