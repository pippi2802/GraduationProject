#!/usr/bin/env bash
# enemy_effectiveness.sh - proves stress/enemy.c actually creates
# interference, independent of the video workload: run stress/victim.c
# (fixed work, pinned to the task's cpu) alone and with enemies running,
# for BOTH a cache victim (buffer = LLC) and a memory victim (buffer =
# 10 x LLC), each matched against the enemy of the same kind - across one
# or more DIAL LEVELS (increasing numbers of competing enemy cores).
#
# Writes two CSVs:
#   --output          per-trial raw data: dial,condition,trial,elapsed_ms
#   --summary-output  one row per dial level: median times, slowdown,
#                      average enemy throughput (GB/s/core) - this is the
#                      one to turn into a thesis table.
#
# --enemy-cpus takes one or more dial levels separated by ';', each a
# comma-separated cpu list, e.g. "2;2,3;2,3,0" runs a 1/2/3-core dial in
# one invocation. A single group with no ';' (e.g. "2,3") runs just that
# one dial level - fully backward compatible with earlier single-dial use.
#
# For a mechanism-level check (does the cache enemy actually cause cache
# pressure rather than memory-bandwidth pressure, and vice versa) use
# verify_targets.sh instead - this script only proves SOMETHING slows down.
set -euo pipefail

VICTIM="" ENEMY="" VICTIM_CPU="" DIALS="" OUTPUT="" SUMMARY_OUTPUT=""
CACHE_SIZE_KB="" MEMORY_SIZE_KB="" STRIDE_BYTES=64 PASSES=50 TRIALS=30
DRY_RUN=0

usage() {
    cat >&2 <<EOF
usage: $0 --victim PATH --enemy PATH --victim-cpu N --enemy-cpus DIALS
          --cache-size-kb N --memory-size-kb N [--stride-bytes N] [--passes N]
          [--trials N] --output RAW_CSV [--summary-output SUMMARY_CSV] [--dry-run]

DIALS: one or more dial levels separated by ';', each a comma-separated cpu
list, e.g. "2;2,3;2,3,0" for a 1/2/3-core dial. A single group ("2,3") runs
just that one dial level.
EOF
    exit 2
}

while [ $# -gt 0 ]; do
    case "$1" in
        --victim) VICTIM="$2"; shift 2 ;;
        --enemy) ENEMY="$2"; shift 2 ;;
        --victim-cpu) VICTIM_CPU="$2"; shift 2 ;;
        --enemy-cpus) DIALS="$2"; shift 2 ;;
        --cache-size-kb) CACHE_SIZE_KB="$2"; shift 2 ;;
        --memory-size-kb) MEMORY_SIZE_KB="$2"; shift 2 ;;
        --stride-bytes) STRIDE_BYTES="$2"; shift 2 ;;
        --passes) PASSES="$2"; shift 2 ;;
        --trials) TRIALS="$2"; shift 2 ;;
        --output) OUTPUT="$2"; shift 2 ;;
        --summary-output) SUMMARY_OUTPUT="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) usage ;;
    esac
done

[ -n "$VICTIM" ] && [ -n "$ENEMY" ] && [ -n "$VICTIM_CPU" ] && [ -n "$DIALS" ] \
    && [ -n "$CACHE_SIZE_KB" ] && [ -n "$MEMORY_SIZE_KB" ] && [ -n "$OUTPUT" ] || usage
[ -n "$SUMMARY_OUTPUT" ] || SUMMARY_OUTPUT="${OUTPUT%.csv}_summary.csv"

LOGDIR="$(mktemp -d)"
trap 'rm -rf "$LOGDIR"' EXIT

start_enemies() {
    local size_kb="$1" cpus="$2"
    ENEMY_PIDS=()
    ENEMY_LOGS=()
    IFS=',' read -ra cpu_list <<< "$cpus"
    for cpu in "${cpu_list[@]}"; do
        local log="$LOGDIR/enemy_cpu${cpu}.log"
        if [ "$DRY_RUN" = "1" ]; then
            echo "[dry-run, background] $ENEMY --size-kb $size_kb --stride-bytes $STRIDE_BYTES --mode rw --cpu $cpu"
        else
            "$ENEMY" --size-kb "$size_kb" --stride-bytes "$STRIDE_BYTES" --mode rw --cpu "$cpu" >"$log" 2>&1 &
            ENEMY_PIDS+=("$!")
            ENEMY_LOGS+=("$log")
        fi
    done
    if [ "$DRY_RUN" != "1" ]; then
        sleep 0.2  # let enemies reach their steady-state loop
        for i in "${!ENEMY_PIDS[@]}"; do
            local pid="${ENEMY_PIDS[$i]}" cpu="${cpu_list[$i]}" psr
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

# Prints each enemy's exit line (so it's still visible live) and returns the
# average of their "(X.XX GB/s)" figures, empty if none parsed.
avg_enemy_gbps() {
    local total=0 n=0 v
    for log in "${ENEMY_LOGS[@]:-}"; do
        [ -f "$log" ] || continue
        cat "$log" >&2  # stderr: stays visible without polluting this function's captured stdout return
        v="$(grep -oE '\([0-9.]+ GB/s\)' "$log" | grep -oE '[0-9.]+' || true)"
        if [ -n "$v" ]; then
            total="$(awk -v t="$total" -v x="$v" 'BEGIN{print t+x}')"
            n=$((n + 1))
        fi
    done
    [ "$n" -gt 0 ] && awk -v t="$total" -v n="$n" 'BEGIN{printf "%.2f", t/n}'
}

run_trials() {
    local condition="$1" victim_size_kb="$2" dial="$3"
    for trial in $(seq 1 "$TRIALS"); do
        if [ "$DRY_RUN" = "1" ]; then
            echo "[dry-run] $VICTIM --size-kb $victim_size_kb --stride-bytes $STRIDE_BYTES --passes $PASSES --cpu $VICTIM_CPU  # dial=$dial $condition trial $trial"
        else
            elapsed_ms="$("$VICTIM" --size-kb "$victim_size_kb" --stride-bytes "$STRIDE_BYTES" \
                --passes "$PASSES" --cpu "$VICTIM_CPU")"
            echo "$dial,$condition,$trial,$elapsed_ms" >> "$OUTPUT"
        fi
    done
}

median_of_condition() {
    local dial="$1" condition="$2"
    awk -F, -v d="$dial" -v c="$condition" '$1==d && $2==c {print $4}' "$OUTPUT" | sort -n | awk '
        { a[NR] = $1 } END { if (NR == 0) { print ""; exit } print a[int((NR + 1) / 2)] }'
}

if [ "$DRY_RUN" != "1" ]; then
    mkdir -p "$(dirname "$OUTPUT")"
    echo "dial,condition,trial,elapsed_ms" > "$OUTPUT"
    mkdir -p "$(dirname "$SUMMARY_OUTPUT")"
    echo "dial,cpus,n_cores,cache_alone_ms,cache_enemy_ms,cache_slowdown,memory_alone_ms,memory_enemy_ms,memory_slowdown,cache_enemy_gbps_avg,memory_enemy_gbps_avg" > "$SUMMARY_OUTPUT"
fi

DIAL_IDX=0
IFS=';' read -ra DIAL_GROUPS <<< "$DIALS"
for CPUS in "${DIAL_GROUPS[@]}"; do
    DIAL_IDX=$((DIAL_IDX + 1))
    IFS=',' read -ra _cpu_count_arr <<< "$CPUS"
    N_CORES=${#_cpu_count_arr[@]}
    echo
    echo "########## dial $DIAL_IDX: cpus=$CPUS ($N_CORES cores) ##########"

    echo "cache victim (${CACHE_SIZE_KB}KB): alone ($TRIALS trials)..."
    run_trials cache_alone "$CACHE_SIZE_KB" "$DIAL_IDX"

    echo "cache victim: with cache enemies on cpus $CPUS ($TRIALS trials)..."
    start_enemies "$CACHE_SIZE_KB" "$CPUS"
    run_trials cache_enemy "$CACHE_SIZE_KB" "$DIAL_IDX"
    CACHE_GBPS=""
    if [ "$DRY_RUN" != "1" ]; then
        stop_enemies
        CACHE_GBPS="$(avg_enemy_gbps)"
    fi

    echo "memory victim (${MEMORY_SIZE_KB}KB): alone ($TRIALS trials)..."
    run_trials memory_alone "$MEMORY_SIZE_KB" "$DIAL_IDX"

    echo "memory victim: with memory enemies on cpus $CPUS ($TRIALS trials)..."
    start_enemies "$MEMORY_SIZE_KB" "$CPUS"
    run_trials memory_enemy "$MEMORY_SIZE_KB" "$DIAL_IDX"
    MEMORY_GBPS=""
    if [ "$DRY_RUN" != "1" ]; then
        stop_enemies
        MEMORY_GBPS="$(avg_enemy_gbps)"
    fi

    if [ "$DRY_RUN" != "1" ]; then
        cache_alone_ms="$(median_of_condition "$DIAL_IDX" cache_alone)"
        cache_enemy_ms="$(median_of_condition "$DIAL_IDX" cache_enemy)"
        memory_alone_ms="$(median_of_condition "$DIAL_IDX" memory_alone)"
        memory_enemy_ms="$(median_of_condition "$DIAL_IDX" memory_enemy)"
        cache_slowdown="$(awk -v a="$cache_alone_ms" -v e="$cache_enemy_ms" 'BEGIN{if(a>0) printf "%.3f", e/a}')"
        memory_slowdown="$(awk -v a="$memory_alone_ms" -v e="$memory_enemy_ms" 'BEGIN{if(a>0) printf "%.3f", e/a}')"
        echo "$DIAL_IDX,\"$CPUS\",$N_CORES,$cache_alone_ms,$cache_enemy_ms,$cache_slowdown,$memory_alone_ms,$memory_enemy_ms,$memory_slowdown,$CACHE_GBPS,$MEMORY_GBPS" >> "$SUMMARY_OUTPUT"
        echo "--- dial $DIAL_IDX: cache ${cache_alone_ms}->${cache_enemy_ms}ms (${cache_slowdown}x, ${CACHE_GBPS} GB/s/core)  memory ${memory_alone_ms}->${memory_enemy_ms}ms (${memory_slowdown}x, ${MEMORY_GBPS} GB/s/core) ---"
    fi
done

if [ "$DRY_RUN" != "1" ]; then
    echo
    echo "wrote $OUTPUT and $SUMMARY_OUTPUT"
fi
