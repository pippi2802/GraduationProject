#!/usr/bin/env bash
# hk_load.sh - housekeeping load generator for cpu0, with a PID file so
# campaign.py can stop it deterministically instead of pkill-by-name.
#
# Usage:
#   hk_load.sh start --cpu 0 --pidfile /tmp/hk_load.pid [--iperf3-server HOST]
#   hk_load.sh stop  --pidfile /tmp/hk_load.pid
set -euo pipefail

usage() {
    echo "usage: $0 start --cpu N --pidfile PATH [--iperf3-server HOST] [--workers N]" >&2
    echo "       $0 stop  --pidfile PATH" >&2
    exit 2
}

CMD="${1:-}"; shift || true
CPU=0
PIDFILE=""
IPERF3_SERVER=""
WORKERS=2

while [ $# -gt 0 ]; do
    case "$1" in
        --cpu) CPU="$2"; shift 2 ;;
        --pidfile) PIDFILE="$2"; shift 2 ;;
        --iperf3-server) IPERF3_SERVER="$2"; shift 2 ;;
        --workers) WORKERS="$2"; shift 2 ;;
        *) usage ;;
    esac
done

[ -n "$PIDFILE" ] || usage

case "$CMD" in
    start)
        if [ -f "$PIDFILE" ]; then
            echo "pidfile $PIDFILE already exists; refusing to start (stop it first)" >&2
            exit 1
        fi
        PIDS=()

        if command -v stress-ng >/dev/null 2>&1; then
            taskset -c "$CPU" stress-ng --io "$WORKERS" --hdd 0 --quiet &
            PIDS+=("$!")
        else
            echo "warning: stress-ng not found, skipping I/O load" >&2
        fi

        if [ -n "$IPERF3_SERVER" ] && command -v iperf3 >/dev/null 2>&1; then
            taskset -c "$CPU" iperf3 -c "$IPERF3_SERVER" -t 0 &
            PIDS+=("$!")
        elif [ -n "$IPERF3_SERVER" ]; then
            echo "warning: iperf3 not found, skipping network load" >&2
        fi

        if [ "${#PIDS[@]}" -eq 0 ]; then
            echo "no load generator available (install stress-ng and/or iperf3)" >&2
            exit 1
        fi

        printf '%s\n' "${PIDS[@]}" > "$PIDFILE"
        echo "started housekeeping load on cpu $CPU, pids: ${PIDS[*]}"
        ;;
    stop)
        if [ ! -f "$PIDFILE" ]; then
            echo "no pidfile $PIDFILE, nothing to stop" >&2
            exit 0
        fi
        while read -r pid; do
            kill "$pid" 2>/dev/null || true
        done < "$PIDFILE"
        rm -f "$PIDFILE"
        echo "stopped housekeeping load"
        ;;
    *)
        usage
        ;;
esac
