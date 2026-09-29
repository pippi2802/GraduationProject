#!/usr/bin/env bash
# verify_targets.sh - proves the cache/memory enemies stress the MECHANISM
# they claim to, using perf hardware counters on the enemy's own core
# (`perf stat -C`), not just that they slow a victim down (that's what
# enemy_effectiveness.sh already measures).
#
# Cache enemy (buffer = LLC): the working set fits in the last-level cache
# after the first touch, so its own core should show a LOW LLC miss rate
# (mostly served from cache) while still occupying/evicting the capacity
# other cores' data would use.
# Memory enemy (buffer = 10x LLC): the working set can never fit, so every
# pass forces a fresh cache-line fetch from DRAM - a HIGH LLC miss rate.
#
# If the two miss rates come out close together, the enemies are NOT
# targeting distinct mechanisms - e.g. because the LLC size it was given is
# wrong, the stride doesn't actually generate the intended traffic, or the
# VM doesn't expose usable PMU counters to the guest (common on some Azure
# sizes; this script fails loudly rather than reporting a meaningless PASS).
set -euo pipefail

ENEMY="" CPU="" CACHE_SIZE_KB="" MEMORY_SIZE_KB="" STRIDE_BYTES=64
DURATION_S=5 OUTPUT="" MIN_GAP_PCT=20

usage() {
    cat >&2 <<EOF
usage: $0 --enemy PATH --cpu N --cache-size-kb N --memory-size-kb N
          [--stride-bytes N] [--duration-s N] [--output CSV] [--min-gap-pct N]
EOF
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --enemy) ENEMY="$2"; shift 2 ;;
        --cpu) CPU="$2"; shift 2 ;;
        --cache-size-kb) CACHE_SIZE_KB="$2"; shift 2 ;;
        --memory-size-kb) MEMORY_SIZE_KB="$2"; shift 2 ;;
        --stride-bytes) STRIDE_BYTES="$2"; shift 2 ;;
        --duration-s) DURATION_S="$2"; shift 2 ;;
        --output) OUTPUT="$2"; shift 2 ;;
        --min-gap-pct) MIN_GAP_PCT="$2"; shift 2 ;;
        *) usage ;;
    esac
done
[ -n "$ENEMY" ] && [ -n "$CPU" ] && [ -n "$CACHE_SIZE_KB" ] && [ -n "$MEMORY_SIZE_KB" ] || usage

if ! command -v perf >/dev/null 2>&1; then
    echo "ERROR: perf not found. Install linux-tools-\$(uname -r) (or linux-tools-generic)." >&2
    echo "       Without it this script cannot tell cache-capacity pressure from memory-bandwidth pressure." >&2
    exit 1
fi

# Probe which events actually resolve on this kernel/VM before using them:
# perf drops the WHOLE run silently if any alias in a combined -e list is
# unknown, so test each alone first and only combine what works.
CANDIDATE_EVENTS="cache-references cache-misses LLC-loads LLC-load-misses"
EVENTS=""
for ev in $CANDIDATE_EVENTS; do
    if perf stat -e "$ev" -- true >/dev/null 2>&1; then
        EVENTS="${EVENTS:+$EVENTS,}$ev"
    else
        echo "[verify_targets] event '$ev' not supported here, skipping" >&2
    fi
done
if [ -z "$EVENTS" ]; then
    echo "ERROR: none of the cache/LLC perf events are available on this VM" >&2
    echo "       (common when the hypervisor doesn't expose the PMU to the guest)." >&2
    echo "       Cannot verify cache-vs-memory targeting here." >&2
    exit 1
fi
echo "[verify_targets] using events: $EVENTS"
[ -n "$OUTPUT" ] && { mkdir -p "$(dirname "$OUTPUT")"; echo "condition,references,misses,miss_rate_pct" > "$OUTPUT"; }

run_condition() {
    local label="$1" size_kb="$2"
    "$ENEMY" --size-kb "$size_kb" --stride-bytes "$STRIDE_BYTES" --mode rw --cpu "$CPU" &
    local pid=$!
    sleep 0.2  # let it reach steady state before counting
    local perf_out
    perf_out="$(perf stat -e "$EVENTS" -C "$CPU" -- sleep "$DURATION_S" 2>&1 || true)"
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true

    echo "=== $label (cpu$CPU, size=${size_kb}KB) ==="
    echo "$perf_out"

    # LAST_ROW is deliberately global (no `local`): run_condition's own
    # stdout must stay directly visible to the terminal, not be swallowed
    # by a capturing command substitution, so the caller reads the row back
    # through this variable instead of piping the function's output.
    LAST_ROW="$(printf '%s\n' "$perf_out" | python3 -c "
import re, sys
label = '$label'
text = sys.stdin.read()
def grab(name):
    m = re.search(r'([\d,]+)\s+' + re.escape(name), text)
    return int(m.group(1).replace(',', '')) if m else None
refs = grab('cache-references') or grab('LLC-loads')
misses = grab('cache-misses')
if misses is None:
    misses = grab('LLC-load-misses')
if refs and misses is not None and refs > 0:
    print(f'{label},{refs},{misses},{100.0*misses/refs:.2f}')
else:
    print(f'{label},,,')
")"
    echo "$LAST_ROW"
    [ -n "$OUTPUT" ] && echo "$LAST_ROW" >> "$OUTPUT"
}

echo "--- cache enemy: expect a LOW LLC miss rate (working set fits) ---"
run_condition cache_enemy "$CACHE_SIZE_KB"
CACHE_ROW="$LAST_ROW"
echo
echo "--- memory enemy: expect a HIGH LLC miss rate (working set never fits) ---"
run_condition memory_enemy "$MEMORY_SIZE_KB"
MEMORY_ROW="$LAST_ROW"

echo
echo "=== verdict ==="
python3 -c "
cache_row = '$CACHE_ROW'.split(',')
memory_row = '$MEMORY_ROW'.split(',')
try:
    cache_rate = float(cache_row[3])
    memory_rate = float(memory_row[3])
except (IndexError, ValueError):
    print('WARN: could not parse miss rates from perf output - inspect the raw output above manually')
    raise SystemExit(0)
gap = memory_rate - cache_rate
print(f'cache_enemy miss rate:  {cache_rate:.2f}%')
print(f'memory_enemy miss rate: {memory_rate:.2f}%')
print(f'gap: {gap:.2f} points (threshold: $MIN_GAP_PCT)')
if gap >= $MIN_GAP_PCT:
    print('PASS: memory enemy misses the cache far more than the cache enemy - they target distinct mechanisms.')
else:
    print('WARN: miss rates are too close - check --cache-size-kb against the REAL LLC size')
    print('      (configs/platform.yaml llc_size_kb), the stride, or whether this VM exposes usable PMU counters.')
"

if [ -n "$OUTPUT" ]; then
    echo
    echo "wrote $OUTPUT"
fi
