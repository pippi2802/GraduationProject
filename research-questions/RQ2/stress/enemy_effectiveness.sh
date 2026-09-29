#!/usr/bin/env bash
# enemy_effectiveness.sh - proves stress/enemy.c actually creates
# interference, independent of the video workload: run stress/victim.c
# (fixed work, pinned to the task's cpu) alone and with enemies running,
# for BOTH a cache victim (buffer = LLC) and a memory victim (buffer =
# 10 x LLC), each matched against the enemy of the same kind. Writes raw
# condition,trial,elapsed_ms rows to --output, then prints a median-based
# slowdown summary (plain stdlib `statistics`, no extra dependency).
#
# For a mechanism-level check (does the cache enemy actually cause cache
# pressure rather than memory-bandwidth pressure, and vice versa) use
# verify_targets.sh instead - this script only proves SOMETHING slows down.
#
# Conditions written: cache_alone, cache_enemy, memory_alone, memory_enemy.
set -euo pipefail

VICTIM="" ENEMY="" VICTIM_CPU="" ENEMY_CPUS="" OUTPUT=""
CACHE_SIZE_KB="" MEMORY_SIZE_KB="" STRIDE_BYTES=64 PASSES=50 TRIALS=30
DRY_RUN=0

usage() {
    cat >&2 <<EOF
usage: $0 --victim PATH --enemy PATH --victim-cpu N --enemy-cpus C1,C2,...
          --cache-size-kb N --memory-size-kb N [--stride-bytes N] [--passes N]
          [--trials N] --output CSV [--dry-run]
EOF
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --victim) VICTIM="$2"; shift 2 ;;
        --enemy) ENEMY="$2"; shift 2 ;;
        --victim-cpu) VICTIM_CPU="$2"; shift 2 ;;
        --enemy-cpus) ENEMY_CPUS="$2"; shift 2 ;;
        --cache-size-kb) CACHE_SIZE_KB="$2"; shift 2 ;;
        --memory-size-kb) MEMORY_SIZE_KB="$2"; shift 2 ;;
        --stride-bytes) STRIDE_BYTES="$2"; shift 2 ;;
        --passes) PASSES="$2"; shift 2 ;;
        --trials) TRIALS="$2"; shift 2 ;;
        --output) OUTPUT="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) usage ;;
    esac
done

[ -n "$VICTIM" ] && [ -n "$ENEMY" ] && [ -n "$VICTIM_CPU" ] && [ -n "$ENEMY_CPUS" ] \
    && [ -n "$CACHE_SIZE_KB" ] && [ -n "$MEMORY_SIZE_KB" ] && [ -n "$OUTPUT" ] || usage

start_enemies() {
    local size_kb="$1"
    ENEMY_PIDS=()
    IFS=',' read -ra cpus <<< "$ENEMY_CPUS"
    for cpu in "${cpus[@]}"; do
        if [ "$DRY_RUN" = "1" ]; then
            echo "[dry-run, background] $ENEMY --size-kb $size_kb --stride-bytes $STRIDE_BYTES --mode rw --cpu $cpu"
        else
            "$ENEMY" --size-kb "$size_kb" --stride-bytes "$STRIDE_BYTES" --mode rw --cpu "$cpu" &
            ENEMY_PIDS+=("$!")
        fi
    done
    if [ "$DRY_RUN" != "1" ]; then
        sleep 0.2  # let enemies reach their steady-state loop
        for i in "${!ENEMY_PIDS[@]}"; do
            local pid="${ENEMY_PIDS[$i]}" cpu="${cpus[$i]}" psr
            psr="$(ps -o psr= -p "$pid" 2>/dev/null | tr -d ' ')"
            if [ "$psr" = "$cpu" ]; then
                echo "[enemy_effectiveness] confirmed: pid $pid running on cpu$cpu"
            else
                echo "[enemy_effectiveness] WARNING: pid $pid reports cpu$psr, expected cpu$cpu"
            fi
        done
    fi
}

stop_enemies() {
    for pid in "${ENEMY_PIDS[@]:-}"; do
        [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    for pid in "${ENEMY_PIDS[@]:-}"; do
        if [ -n "$pid" ]; then
            if kill -0 "$pid" 2>/dev/null; then
                echo "[enemy_effectiveness] WARNING: pid $pid still alive after stop"
            else
                echo "[enemy_effectiveness] confirmed: pid $pid stopped"
            fi
        fi
    done
}

run_trials() {
    local condition="$1" victim_size_kb="$2"
    for trial in $(seq 1 "$TRIALS"); do
        if [ "$DRY_RUN" = "1" ]; then
            echo "[dry-run] $VICTIM --size-kb $victim_size_kb --stride-bytes $STRIDE_BYTES --passes $PASSES --cpu $VICTIM_CPU  # $condition trial $trial"
        else
            elapsed_ms="$("$VICTIM" --size-kb "$victim_size_kb" --stride-bytes "$STRIDE_BYTES" \
                --passes "$PASSES" --cpu "$VICTIM_CPU")"
            echo "$condition,$trial,$elapsed_ms" >> "$OUTPUT"
        fi
    done
}

if [ "$DRY_RUN" != "1" ]; then
    mkdir -p "$(dirname "$OUTPUT")"
    echo "condition,trial,elapsed_ms" > "$OUTPUT"
fi

echo "cache victim (${CACHE_SIZE_KB}KB): alone ($TRIALS trials)..."
run_trials cache_alone "$CACHE_SIZE_KB"

echo "cache victim: with cache enemies on cpus $ENEMY_CPUS ($TRIALS trials)..."
start_enemies "$CACHE_SIZE_KB"
run_trials cache_enemy "$CACHE_SIZE_KB"
[ "$DRY_RUN" = "1" ] || stop_enemies

echo "memory victim (${MEMORY_SIZE_KB}KB): alone ($TRIALS trials)..."
run_trials memory_alone "$MEMORY_SIZE_KB"

echo "memory victim: with memory enemies on cpus $ENEMY_CPUS ($TRIALS trials)..."
start_enemies "$MEMORY_SIZE_KB"
run_trials memory_enemy "$MEMORY_SIZE_KB"
[ "$DRY_RUN" = "1" ] || stop_enemies

if [ "$DRY_RUN" != "1" ]; then
    echo "wrote $OUTPUT"
    echo
    echo "=== summary (median elapsed_ms, slowdown = enemy / alone) ==="
    python3 -c "
import csv, statistics
from collections import defaultdict

by_condition = defaultdict(list)
with open('$OUTPUT', newline='') as f:
    for row in csv.DictReader(f):
        by_condition[row['condition']].append(float(row['elapsed_ms']))

medians = {c: statistics.median(v) for c, v in by_condition.items()}
for c, m in medians.items():
    print(f'{c}: median={m:.2f}ms (n={len(by_condition[c])})')
for kind in ('cache', 'memory'):
    alone, enemy = medians.get(f'{kind}_alone'), medians.get(f'{kind}_enemy')
    if alone and enemy:
        print(f'{kind} slowdown: {enemy/alone:.2f}x')
"
fi
