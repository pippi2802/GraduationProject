#!/usr/bin/env bash
# osnoise_capture.sh - capture `rtla osnoise` output on the RT cores for a
# given duration, to characterize OS noise independent of the workload.
# Fails loudly if rtla is missing rather than silently skipping: an absent
# osnoise capture should never be mistaken for "zero noise measured".
#
# Usage: osnoise_capture.sh --cpus 1,2,3 --duration-s 60 \
#            --mode top|hist --output results/derived/osnoise/run.txt
set -euo pipefail

CPUS=""
DURATION_S=60
MODE="hist"
OUTPUT=""

usage() {
    echo "usage: $0 --cpus 1,2,3 --duration-s N --mode top|hist --output PATH" >&2
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --cpus) CPUS="$2"; shift 2 ;;
        --duration-s) DURATION_S="$2"; shift 2 ;;
        --mode) MODE="$2"; shift 2 ;;
        --output) OUTPUT="$2"; shift 2 ;;
        *) usage ;;
    esac
done

[ -n "$CPUS" ] && [ -n "$OUTPUT" ] || usage

if ! command -v rtla >/dev/null 2>&1; then
    echo "ERROR: rtla not found on PATH. Install linux-tools (rtla) to capture osnoise;" >&2
    echo "       this script refuses to silently skip the measurement." >&2
    exit 1
fi

case "$MODE" in
    top|hist) ;;
    *) echo "ERROR: --mode must be 'top' or 'hist'" >&2; exit 2 ;;
esac

mkdir -p "$(dirname "$OUTPUT")"

echo "running: rtla osnoise $MODE -c $CPUS -d ${DURATION_S}s"
rtla osnoise "$MODE" -c "$CPUS" -d "${DURATION_S}s" > "$OUTPUT" 2>&1
echo "wrote $OUTPUT"
