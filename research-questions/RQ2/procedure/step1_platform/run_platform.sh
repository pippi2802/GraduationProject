#!/usr/bin/env bash
# Step 1 on the VM (the VM type you will deploy on), from this folder, once per VM type, independent of the workload.
#
#   ./run_platform.sh --victim-cpu 1 --enemy-cpus "2;2,3;2,3,0"  [--trials 20] [--passes 50]
#                     [--noise-period-ms 41.667 --noise-cpu 1 [--noise-jobs 20000]]        (P3, run as root)
#
# --victim-cpu    an RT core where the workload would run
# --enemy-cpus    the dial: enemy cores for m = 1, 2, 3, separated by ';', each a comma list ("2;2,3;2,3,0" = 1, 2, 3 enemy cores).
#                 Never a core of the victim; use the cores your workload leaves free.
# --cache-kb / --memory-kb  victim and enemy buffer sizes; default = the last-level cache and 10 x the last-level cache
#                 (check with lscpu on VMs with several L3 instances)
#
# What it does: builds the victim and the enemy (make), runs each victim alone and with the enemies for every dial level
# (P1 + P2: results/victim_raw.csv, results/victim_summary.csv), runs the empty-job loop if asked (P3: results/noise_floor/), and
# computes results/platform_factor.csv (alpha_platform(m)) and results/noise_floor_summary.csv, which step 4 reads.
set -euo pipefail
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
cd "$(dirname "$SELF")"

VICTIM_CPU="" ENEMY_CPUS="" TRIALS=20 PASSES=50 CACHE_KB="" MEMORY_KB="" NOISE_PERIOD="" NOISE_CPU="" NOISE_JOBS=20000
while [ $# -gt 0 ]; do
    case "$1" in
        --victim-cpu) VICTIM_CPU="$2"; shift 2 ;;
        --enemy-cpus) ENEMY_CPUS="$2"; shift 2 ;;
        --trials) TRIALS="$2"; shift 2 ;;
        --passes) PASSES="$2"; shift 2 ;;
        --cache-kb) CACHE_KB="$2"; shift 2 ;;
        --memory-kb) MEMORY_KB="$2"; shift 2 ;;
        --noise-period-ms) NOISE_PERIOD="$2"; shift 2 ;;
        --noise-cpu) NOISE_CPU="$2"; shift 2 ;;
        --noise-jobs) NOISE_JOBS="$2"; shift 2 ;;
        *) sed -n 2,19p "$SELF"; exit 2 ;;
    esac
done
[ -n "$VICTIM_CPU" ] && [ -n "$ENEMY_CPUS" ] || { sed -n 2,19p "$SELF"; exit 2; }

if [ -z "$CACHE_KB" ]; then
    llc_bytes=$(getconf LEVEL3_CACHE_SIZE 2>/dev/null || echo 0)
    [ "$llc_bytes" -gt 0 ] || llc_bytes=$(getconf LEVEL2_CACHE_SIZE)
    CACHE_KB=$((llc_bytes / 1024))
fi
[ -n "$MEMORY_KB" ] || MEMORY_KB=$((CACHE_KB * 10))
echo "victim cpu $VICTIM_CPU, enemy dial \"$ENEMY_CPUS\", cache buffer ${CACHE_KB} KB, memory buffer ${MEMORY_KB} KB, $TRIALS trials, $PASSES passes"

make -s
mkdir -p results
rm -f results/victim_raw.csv results/victim_summary.csv
./enemy_effectiveness.sh --victim ./victim --enemy ./enemy --victim-cpu "$VICTIM_CPU" --enemy-cpus "$ENEMY_CPUS" \
    --cache-size-kb "$CACHE_KB" --memory-size-kb "$MEMORY_KB" --trials "$TRIALS" --passes "$PASSES" \
    --output results/victim_raw.csv --summary-output results/victim_summary.csv

if [ -n "$NOISE_PERIOD" ]; then
    python3 noise_floor.py --period-ms "$NOISE_PERIOD" --jobs "$NOISE_JOBS" ${NOISE_CPU:+--cpu "$NOISE_CPU"} --output results/noise_floor/instance0.csv
fi
python3 compute_platform.py
