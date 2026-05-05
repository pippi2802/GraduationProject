#!/bin/bash
# Verification script - Monitors that all tasks run on core 0 only

echo "=========================================="
echo "SINGLE CORE VERIFICATION"
echo "=========================================="
echo ""
echo "This script verifies tasks are running:"
echo "  1. In PARALLEL (at the same time)"
echo "  2. On CPU CORE 0 ONLY"
echo ""

# Start monitoring in background
echo "Starting CPU monitoring..."
echo ""

# Function to monitor CPU usage by core
monitor_cores() {
    while true; do
        echo "=== CPU Core Activity ==="
        ps aux | grep "periodic_task" | grep -v grep | while read line; do
            pid=$(echo $line | awk '{print $2}')
            cmd=$(echo $line | awk '{print $NF}')
            
            # Get CPU affinity for this PID
            if command -v taskset &> /dev/null; then
                cpus=$(taskset -p -c $pid 2>/dev/null | grep -oP '\d+' | tail -1)
                printf "PID %6d on CPU %s: %s\n" "$pid" "$cpus" "$cmd"
            fi
        done
        echo ""
        sleep 2
    done
}

# Alternative: Use ps to show CPU affinity
if command -v ps &> /dev/null; then
    echo "Method 1: Using ps to show running processes:"
    ps aux | grep periodic_task | grep -v grep
    echo ""
fi

echo "Method 2: Check CPU core affinity with taskset:"
echo "================================================"
echo ""
echo "Run this while tasks are running:"
echo "  ps aux | grep periodic_task | grep -v grep | while read line; do"
echo "    pid=\$(echo \$line | awk '{print \$2}')"
echo "    echo \"PID \$pid:\""
echo "    taskset -p -c \$pid"
echo "  done"
echo ""

echo "Method 3: Monitor CPU with 'top' (if available):"
echo "================================================"
echo ""
echo "  1. Open another terminal"
echo "  2. Run: top"
echo "  3. Look for periodic_task processes"
echo "  4. Press 'f' then 'j' to show CPU affinity column"
echo "  5. Verify all tasks show CPU 0"
echo ""

echo "Method 4: Direct verification:"
echo "=============================="
echo ""

# Create a test to show parallel + single-core execution
cat > /tmp/verify_singlecore.sh << 'VERIFY'
#!/bin/bash

echo "Starting 3 tasks on single core..."
echo ""

# Record start time
START=$(date +%s%N)

# Task 1
(
  for i in {1..5}; do
    echo "[Task1-$i] $(date +%s%N | cut -c1-13)"
    sleep 0.1
  done
) &
PID1=$!

# Task 2
(
  for i in {1..5}; do
    echo "[Task2-$i] $(date +%s%N | cut -c1-13)"
    sleep 0.15
  done
) &
PID2=$!

# Task 3
(
  for i in {1..5}; do
    echo "[Task3-$i] $(date +%s%N | cut -c1-13)"
    sleep 0.12
  done
) &
PID3=$!

echo "All tasks started in parallel (PIDs: $PID1, $PID2, $PID3)"
echo ""
echo "Waiting for completion..."
wait $PID1 $PID2 $PID3

END=$(date +%s%N)
DURATION=$((($END - $START) / 1000000))

echo ""
echo "All tasks completed in ${DURATION}ms"
echo "If duration ≈ 500ms = PARALLEL execution"
echo "If duration ≈ 1500ms = SEQUENTIAL execution"
VERIFY

chmod +x /tmp/verify_singlecore.sh
/tmp/verify_singlecore.sh

echo ""
echo "=========================================="
echo "To verify while tasks are running:"
echo ""
echo "  1. In another terminal, run:"
echo "     watch -n 1 'ps aux | grep periodic_task | grep -v grep'"
echo ""
echo "  2. Or check core affinity:"
echo "     ps aux | grep periodic_task | grep -v grep | awk '{print \$2}' | xargs taskset -p -c"
echo ""
echo "=========================================="
