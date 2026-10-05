#!/usr/bin/env bash
# status.sh [multi_core|single_core]        (default: both)
#
# Read-only snapshot of a running validation: is the script alive, how many of the 12 runs are collected, which pod
# is running and for how long, whether the workload and the enemy really run on the node, and when it should finish.
# It changes nothing, so it is safe to run at any time, as often as you like.
#
#   validation/status.sh
#   watch -n 60 validation/status.sh single_core
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_MIN="${RUN_MIN:-35.3}"          # minutes per run seen in the real runs (50000 jobs); 21.3 for 30000 jobs
WORKLOAD_NS="${WORKLOAD_NS:-rq2}"

status_one() {
    local SCEN="$1" NODE NS SHORT
    case "$SCEN" in
        multi_core)  NODE="${NODE_MULTI:-rt-k8s-worker-6}"; NS="rq2-node-prep-worker6"; SHORT=multi ;;
        single_core) NODE="${NODE_SINGLE:-rt-k8s-worker-7}"; NS="rq2-node-prep-worker7"; SHORT=single ;;
        *) echo "usage: status.sh [multi_core|single_core]" >&2; return 2 ;;
    esac
    local RES="$HERE/results/$SCEN" total done_n alive pods cur name phase start intf now elapsed_min agent ps_out warn=()
    total=$(find "$HERE/manifests/$SCEN" -name '*.yaml' 2>/dev/null | wc -l)
    done_n=$(find "$RES" -name .done 2>/dev/null | wc -l)
    now=$(date -u +%s)

    echo "== $SCEN on $NODE   ($(date -u +%H:%M) UTC)"
    if pgrep -f "run_validation.sh $SCEN" > /dev/null; then alive=yes; else alive=NO; fi
    echo "   script alive : $alive"
    echo "   collected    : $done_n of $total runs"
    if [ -f "$RES/summary.tsv" ]; then
        echo "   last results : $(tail -n 3 "$RES/summary.tsv" | awk '{printf "%s/%s_%s=%s  ", $2, $3, $4, $5}')"
        if grep -q FAILED "$RES/summary.tsv"; then warn+=("some run is marked FAILED in summary.tsv"); fi
    fi

    pods=$(kubectl -n "$WORKLOAD_NS" get pod -l validation=true -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.phase}{" "}{.status.startTime}{" "}{.metadata.labels.interference}{"\n"}{end}' 2>/dev/null | grep "^rq2-val-$SHORT-" || true)
    local cur_left=0
    if [ -n "$pods" ]; then
        read -r name phase start intf <<< "$(echo "$pods" | head -1)"
        elapsed_min=$(( (now - $(date -u -d "$start" +%s)) / 60 ))
        echo "   running now  : $name   $phase for $elapsed_min min   (interference: $intf)"
        cur_left=$(awk -v r="$RUN_MIN" -v e="$elapsed_min" 'BEGIN{x=r-e; print (x<0?0:x)}')
        case "$phase" in Running|Succeeded) ;; *) warn+=("pod phase is $phase") ;; esac
        if [ "$elapsed_min" -gt 45 ]; then warn+=("the pod is running for more than 45 min, slower than the ~36 min of a run"); fi
        agent=$(kubectl -n "$NS" get pod -l app=rq1-agent --field-selector "spec.nodeName=$NODE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
        if [ -n "$agent" ]; then
            ps_out=$(timeout 25 kubectl -n "$NS" exec "$agent" -- nsenter --target 1 --mount --pid -- \
                     bash -c 'ps -eo pid,psr,pcpu,etime,args | grep -E "[r]t_video|[l]aunch.py|[r]q2-enemy"' 2>/dev/null || true)
            echo "   on the node  :"
            if [ -n "$ps_out" ]; then echo "$ps_out" | awk '{n=split($0,a," "); printf "      cpu%s  %5s%% cpu  up %s  %s %s\n", $2, $3, $4, $5, $6}'; else echo "      (no workload or enemy process found)"; fi
            if [ "$intf" = memory ] && ! echo "$ps_out" | grep -q "rq2-enemy"; then warn+=("a memory run is going but no rq2-enemy process is running"); fi
            if [ "$intf" = none ] && echo "$ps_out" | grep -q "rq2-enemy"; then warn+=("an enemy is running during a run without interference"); fi
            if ! echo "$ps_out" | grep -qE "rt_video|launch.py"; then warn+=("the pod is $phase but no workload process is seen on the node"); fi
        else
            warn+=("no node-prep agent on $NODE, cannot look at the node")
        fi
    else
        echo "   running now  : no validation pod (between two runs, or finished)"
    fi

    local remaining=$((total - done_n))
    if [ "$remaining" -gt 0 ]; then
        local more=$remaining
        [ -n "$pods" ] && more=$((remaining - 1))
        local eta_min
        eta_min=$(awk -v c="$cur_left" -v m="$more" -v r="$RUN_MIN" 'BEGIN{printf "%d", c + m * (r + 0.2)}')
        echo "   expected end : about $(date -u -d "@$((now + eta_min * 60))" +%H:%M) UTC   (in $((eta_min / 60)) h $((eta_min % 60)) min, if no run is repeated)"
        if [ "$alive" = NO ]; then warn+=("the script is NOT running but runs are missing${pods:+ (a pod is still running, but nobody will collect it)}: start it again, collected runs are skipped"); fi
    else
        echo "   all runs collected"
    fi
    echo "   last log line: $(tail -n 1 "$RES/validation.log" 2>/dev/null | cut -c1-110)"
    if [ ${#warn[@]} -gt 0 ]; then for w in "${warn[@]}"; do echo "   !! $w"; done; else echo "   no problems seen"; fi
    echo
}

if [ -n "${1:-}" ]; then status_one "$1"; else status_one multi_core; status_one single_core; fi
