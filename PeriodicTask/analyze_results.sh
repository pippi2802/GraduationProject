#!/bin/bash
# Comprehensive analysis script for periodic task results

RESULTS_DIR="cfs_results_80"

echo "=========================================="
echo "PERIODIC TASK ANALYSIS"
echo "=========================================="
echo ""

# Compile analysis tools if not already done
if [ ! -f "Tools/cdf" ]; then
    echo "Compiling analysis tools..."
    gcc -o Tools/cdf Tools/cdf.c
    gcc -o Tools/dlmiss Tools/dlmiss.c
fi

# Function to analyze a task file
analyze_task() {
    local task_file=$1
    local task_num=$2
    local period=$3
    
    echo ""
    echo "========== TASK $task_num ANALYSIS ==========="
    echo "Period: $period μs"
    echo ""
    
    # Basic statistics
    echo "--- Execution Time Statistics ---"
    awk 'NF>0 && NF>=6 {
        cpu = $5
        sum += cpu
        if (NR == 1 || cpu > max) max = cpu
        if (NR == 1 || cpu < min) min = cpu
        n++
    }
    END {
        if (n > 0) {
            printf "Iterations: %d\n", n
            printf "Min: %.0f μs\n", min
            printf "Max: %.0f μs\n", max
            printf "Avg: %.2f μs\n", sum/n
            printf "Std Dev: %.2f μs\n", sqrt((sum2/n) - (sum/n)*(sum/n))
        }
    }' <(awk '{cpu=$5; sum2+=cpu*cpu; print}' "$task_file") "$task_file"
    
    # Deadline miss analysis
    echo ""
    echo "--- Deadline Miss Analysis ---"
    local misses=$(awk 'NF>=4 && $4>0 {count++} END {print count+0}' "$task_file")
    local total=$(awk 'NF>0 {count++} END {print count+0}' "$task_file")
    echo "Deadline Misses: $misses / $total ($(( misses * 100 / total ))%)"
    
    # CPU time distribution (CDF)
    echo ""
    echo "--- Execution Time CDF ---"
    cut -d' ' -f5 "$task_file" | Tools/cdf | head -5
    echo "..."
    cut -d' ' -f5 "$task_file" | Tools/cdf | tail -5
    
    # Save full CDF
    cut -d' ' -f5 "$task_file" | Tools/cdf > "${task_file%.txt}_cdf.txt"
    echo "Full CDF saved to: ${task_file%.txt}_cdf.txt"
}

# Analyze each task
if [ -f "$RESULTS_DIR/task1.txt" ]; then
    analyze_task "$RESULTS_DIR/task1.txt" "1 (High Priority)" "100000"
fi

if [ -f "$RESULTS_DIR/task2.txt" ]; then
    analyze_task "$RESULTS_DIR/task2.txt" "2 (Medium Priority)" "200000"
fi

if [ -f "$RESULTS_DIR/task3.txt" ]; then
    analyze_task "$RESULTS_DIR/task3.txt" "3 (Low Priority)" "300000"
fi

# Comparison
echo ""
echo "========== CROSS-TASK COMPARISON =========="

echo ""
echo "Average Execution Times:"
for f in "$RESULTS_DIR"/task*.txt; do
    if [ -f "$f" ]; then
        task=$(basename "$f" .txt)
        avg=$(awk 'NF>=5 {sum+=$5; n++} END {printf "%.0f", sum/n}' "$f")
        echo "  $task: $avg μs"
    fi
done

echo ""
echo "Deadline Miss Percentages:"
for f in "$RESULTS_DIR"/task*.txt; do
    if [ -f "$f" ]; then
        task=$(basename "$f" .txt)
        misses=$(awk '$6>0 {count++} END {print count+0}' "$f")
        total=$(awk 'END {print NR}' "$f")
        pct=$(( misses * 100 / total ))
        echo "  $task: $pct% ($misses/$total)"
    fi
done

echo ""
echo "=========================================="
echo "Analysis complete!"
echo "CDFs saved for each task."
echo "=========================================="
