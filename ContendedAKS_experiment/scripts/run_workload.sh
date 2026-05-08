#!/bin/sh
# Container entrypoint. Runs rt_multi_periodic with 3 tasks and samples
# /proc/stat in the background.
#
# Env vars (with defaults). Each TASK_i is "<period_us>:<runtime_us>:<iters>".
#   PREFIX     : output filename prefix (e.g. "cA" or "cB")
#   TASK_1     : default 20000:5000:1500     (T=20ms, C=5ms,  U=0.25)
#   TASK_2     : default 50000:15000:600     (T=50ms, C=15ms, U=0.30)
#   TASK_3     : default 100000:25000:300    (T=100ms,C=25ms, U=0.25)
#   OUT_DIR    : default /out
#   SAMPLE_HZ  : default 1
#   HOLD_SEC   : default 36000   (keep container alive after run for kubectl cp)

set -eu

PREFIX="${PREFIX:-cX}"
TASK_1="${TASK_1:-20000:5000:1500}"
TASK_2="${TASK_2:-50000:15000:600}"
TASK_3="${TASK_3:-100000:25000:300}"
OUT_DIR="${OUT_DIR:-/out}"
SAMPLE_HZ="${SAMPLE_HZ:-1}"
HOLD_SEC="${HOLD_SEC:-36000}"

mkdir -p "$OUT_DIR"

# Background sampler: aggregate "cpu" line + per-cpu lines.
(
    echo "ts_ns,line"
    while true; do
        ts=$(date +%s%N)
        awk -v ts="$ts" '/^cpu/ {print ts","$0}' /proc/stat
        sleep "$(awk -v hz="$SAMPLE_HZ" 'BEGIN{ printf "%f", 1.0/hz }')"
    done
) > "$OUT_DIR/${PREFIX}_proc_stat.csv" &
SAMPLER_PID=$!
trap 'kill $SAMPLER_PID 2>/dev/null || true' EXIT INT TERM

echo "[${PREFIX}] starting tasks: $TASK_1 | $TASK_2 | $TASK_3"
/usr/local/bin/rt_multi_periodic "$OUT_DIR" "$PREFIX" \
    "$TASK_1" "$TASK_2" "$TASK_3"

kill $SAMPLER_PID 2>/dev/null || true
wait 2>/dev/null || true
echo "[${PREFIX}] done. Sleeping ${HOLD_SEC}s so results can be copied out."
# Keep the container alive so kubectl cp can fetch results before pod GC.
sleep "$HOLD_SEC"
