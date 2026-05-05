#!/bin/sh
# Runs the periodic workload while sampling /proc/stat (steal time) in the background.
# Outputs two files under /out:
#   - rt_periodic.csv : per-invocation timing (CSV from rt_periodic)
#   - proc_stat.csv   : timestamped cpu line from /proc/stat (1 Hz)
# Env vars (with defaults):
#   PERIOD_US=10000  RUNTIME_US=2000  ITERS=1500  OUT_DIR=/out  SAMPLE_HZ=1

set -eu

PERIOD_US="${PERIOD_US:-10000}"
RUNTIME_US="${RUNTIME_US:-2000}"
ITERS="${ITERS:-1500}"
OUT_DIR="${OUT_DIR:-/out}"
SAMPLE_HZ="${SAMPLE_HZ:-1}"

mkdir -p "$OUT_DIR"

# Background sampler: aggregate "cpu" line + per-cpu lines, with monotonic timestamp.
(
    echo "ts_ns,line"
    while true; do
        ts=$(awk 'BEGIN{ "date +%s%N" | getline t; print t }')
        # Capture only the lines starting with "cpu" (aggregate + per-cpu).
        awk -v ts="$ts" '/^cpu/ {print ts","$0}' /proc/stat
        # crude rate control
        sleep "$(awk -v hz="$SAMPLE_HZ" 'BEGIN{ printf "%f", 1.0/hz }')"
    done
) > "$OUT_DIR/proc_stat.csv" &
SAMPLER_PID=$!
trap 'kill $SAMPLER_PID 2>/dev/null || true' EXIT INT TERM

# Run the workload to completion.
/usr/local/bin/rt_periodic "$PERIOD_US" "$RUNTIME_US" "$ITERS" > "$OUT_DIR/rt_periodic.csv"

# Stop sampler.
kill $SAMPLER_PID 2>/dev/null || true
wait 2>/dev/null || true
echo "done"
