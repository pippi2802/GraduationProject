#!/usr/bin/env bash
# Online validation of the audio workload: runs the 28 pods of pods/ one after the other, unattended, and saves the data in results/.
#
#   nohup ./run_validation.sh > run_validation.out 2>&1 &        both scenarios at the same time, each on its own node (about 2.3 h)
#   ./run_validation.sh --scenario single_core                    only one scenario        (--route route1|route2b|hwm: only that route)
#   DRY_RUN=1 ./run_validation.sh                                 prints the plan and touches nothing
#   tail -f results/single_core/validation.log                    progress (and results/multi_core/validation.log)
#
# For every run (order: p1e-3, then p1e-2, then p1e-1; inside each, route1 then route2b, without then with interference; HWM last):
# the memory enemy is started first when the run is a _memory one (confirmed to burn cpu), the pod is applied as it is in pods/ (already
# pinned to its node), its phase is polled until it ends (a failed pod is seen at once, with its state and logs in the log), the CSV and meta.json
# of every instance are pulled through the node-prep agent into results/<scenario>/<route>/<p>_<interference>/, checked (row count = jobs,
# SCHED_FIFO / affinity / mlock flags true), the number of misses is logged, the pod is deleted, the enemy is stopped (confirmed) and the script
# settles for 10 s.
#   - safe to restart: a finished run (.done in its folder) is skipped; a failed run is retried once, then recorded as FAILED in summary.tsv
#   - it refuses to start if a pod of this validation (label validation=true) or of the profiling (rq2-single-instance0, rq2-multi) exists,
#     if no node-prep agent is found for a node, or if an rq2-enemy is already running there
#   - before the first run of a scenario it checks the node's kubepods-besteffort.slice: it must hold the period of these pods (10000 us), because a
#     slice left with another workload's period makes a two-core pod fail with StartError. If it holds another period it is reset (runtime 0,
#     then the period) - no pod is running at that moment. --no-slice-reset leaves it alone.
#   - Ctrl-C or `pkill -TERM -f "[r]un_validation.sh"` stops everything and the enemies; the exit trap stops an enemy whatever happens
# Needs kubectl, python3, the node-prep agent pods (label app=rq1-agent, namespace rq2-node-prep-worker<N>) and ../../stress1/campaign_{start,stop}_enemies.sh.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STRESS="$HERE/../../stress1"
NODE_DIR="${NODE_DIR:-/var/lib/rq2/results/audio_validation}"
MEM_KB="${MEM_KB:-2662400}" STRIDE=64 SETTLE_S="${SETTLE_S:-10}" ATTEMPTS="${ATTEMPTS:-2}" DRY_RUN="${DRY_RUN:-0}"
SCENARIOS="single_core multi_core" ROUTE="" SLICE_RESET=1
while [ $# -gt 0 ]; do
    case "$1" in
        --scenario) SCENARIOS="$2"; shift 2 ;; --route) ROUTE="$2"; shift 2 ;; --no-slice-reset) SLICE_RESET=0; shift ;;
        *) sed -n '2,/^set /p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'; exit 2 ;;
    esac
done

plan() {   # <scenario>: run_id|pod_file|node|interference|enemy_cpus|save_dir|jobs|period_us, in the order of the validation
    python3 - "$HERE/runs.csv" "$1" "$ROUTE" <<'PY'
import csv, sys
rows = [r for r in csv.DictReader(open(sys.argv[1])) if r["scenario"] == sys.argv[2] and (not sys.argv[3] or r["route"] == sys.argv[3])]
p, route = {"0.001": 0, "0.01": 1, "0.1": 2, "all": 3}, {"route1": 0, "route2b": 1, "hwm": 2}
for r in sorted(rows, key=lambda r: (p[r["p"]], route[r["route"]], r["interference"] != "none")):
    print("|".join([r["run_id"], r["pod_file"], r["node"], r["interference"], r["enemy_cpus"], r["save_results_in"], r["jobs"], r["period_us"]]))
PY
}

validate_scenario() {   # <scenario>: runs in its own subshell, so its variables and traps are its own
    SC="$1"
    LOGDIR="$HERE/results/$SC"; LOG="$LOGDIR/validation.log"; SUMMARY="$LOGDIR/summary.tsv"
    if [ "$DRY_RUN" = 1 ]; then LOG=/dev/null; else mkdir -p "$LOGDIR"; fi
    say() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SC: $*" | tee -a "$LOG"; }
    mapfile -t RUNS < <(plan "$SC")
    [ ${#RUNS[@]} -gt 0 ] || { say "no runs in runs.csv for $SC ${ROUTE:+route $ROUTE}"; return 1; }
    IFS='|' read -r _ _ NODE _ _ _ _ PERIOD <<< "${RUNS[0]}"
    NS="rq2-node-prep-worker${NODE##*-}"
    say "start: ${#RUNS[@]} runs on $NODE (agent namespace $NS)"
    if [ "$DRY_RUN" = 1 ]; then
        for r in "${RUNS[@]}"; do
            IFS='|' read -r id pod node cond cpus out jobs period <<< "$r"
            if [ "$cond" = memory ]; then desc="memory enemy on cpus $cpus"; else desc="no enemy"; fi
            say "[dry-run] $id: $pod, $desc -> $out"
        done
        return 0
    fi
    AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent --field-selector "spec.nodeName=$NODE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    [ -n "$AGENT" ] || { say "FATAL: no node-prep agent (label app=rq1-agent) on $NODE in $NS"; return 1; }
    on_node() { kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --pid -- "$@"; }
    stop_enemies() { local o; o=$(on_node bash -s -- < "$STRESS/campaign_stop_enemies.sh" 2>&1) || true; echo "$o" | grep -q STILL_ALIVE && { say "FATAL: an enemy could not be stopped on $NODE"; return 1; }; return 0; }
    trap stop_enemies EXIT; trap 'exit 130' INT TERM                    # whatever happens, no enemy is left running
    stop_enemies || return 1                                             # clean start
    on_node bash -c 'pgrep -x rq2-enemy' > /dev/null 2>&1 && { say "FATAL: an rq2-enemy is still running on $NODE"; return 1; }

    if [ "$SLICE_RESET" = 1 ]; then       # the slice must hold the period of these pods
        say "node slice: $(on_node bash -s -- "$PERIOD" <<'EOS' 2>&1 | tr '\n' ' '
d=/sys/fs/cgroup/kubepods.slice/kubepods-besteffort.slice
now=$(cat $d/cpu.rt_period_us)
echo "period $now runtime $(cat $d/cpu.rt_runtime_us)"
if [ "$now" != "$1" ]; then
    if echo 0 > $d/cpu.rt_runtime_us && echo "$1" > $d/cpu.rt_period_us; then echo "-> reset to period $(cat $d/cpu.rt_period_us)"; else echo "RESET FAILED"; fi
fi
EOS
)"
        say "(a slice at the pods' period is what a two-core pod needs; a different period is reset here)"
    fi

    FAILED=()
    for r in "${RUNS[@]}"; do
        IFS='|' read -r ID POD_FILE _ COND CPUS OUT JOBS _ <<< "$r"
        DIR="$HERE/$OUT"
        if [ -f "$DIR/.done" ]; then say "$ID: already collected, skipped"; continue; fi
        INST=$(grep -o 'cpus=\[[0-9,]*\]' "$HERE/$POD_FILE" | head -1 | tr -cd ',' | wc -c); INST=$((INST + 1))
        say "=== $ID ($COND, $INST instance(s), $JOBS jobs)"
        if kubectl -n rq2 get pod "$ID" > /dev/null 2>&1; then say "FATAL: pod $ID already exists"; return 1; fi
        ok=0
        for try in $(seq 1 "$ATTEMPTS"); do
            if [ "$COND" = memory ]; then
                o=$(on_node bash -s -- "$MEM_KB" "$STRIDE" "$CPUS" < "$STRESS/campaign_start_enemies.sh" 2>&1); echo "$o" | sed 's/^/    /' >> "$LOG"
                if echo "$o" | grep -qE "MISSING|LOW_CPU"; then say "FATAL: an enemy is not running (install it on the node first)"; return 1; fi
            fi
            if kubectl apply -f "$HERE/$POD_FILE" > /dev/null 2>&1 && wait_pod "$ID" $((JOBS / 100 + 900)) && pull "$ID" "$DIR" "$INST" && check "$DIR" "$INST" "$JOBS"; then ok=1; fi
            [ "$ok" = 1 ] || { say "attempt $try failed"; diag "$ID"; }
            kubectl -n rq2 delete pod "$ID" --ignore-not-found > /dev/null 2>&1
            [ "$COND" = memory ] && { stop_enemies || return 1; }
            [ "$ok" = 1 ] && break
        done
        if [ "$ok" = 1 ]; then
            cp "$HERE/$POD_FILE" "$DIR/manifest.yaml"; touch "$DIR/.done"
            say "$ID done: $(misses "$DIR" "$INST")"; printf '%s\t%s\tdone\n' "$ID" "$(date -u +%FT%TZ)" >> "$SUMMARY"
        else
            FAILED+=("$ID"); say "$ID FAILED after $ATTEMPTS attempt(s): data missing or incomplete, do not trust it"; printf '%s\t%s\tFAILED\n' "$ID" "$(date -u +%FT%TZ)" >> "$SUMMARY"
        fi
        sleep "$SETTLE_S"
    done
    [ ${#FAILED[@]} -eq 0 ] && { say "all ${#RUNS[@]} runs collected"; return 0; } || { say "FAILED runs: ${FAILED[*]} (start the script again: collected runs are skipped)"; return 1; }
}

wait_pod() {   # <pod> <timeout s>: 0 when the pod Succeeded; 1 when it Failed or the time ran out (a failed pod is seen at once)
    local t=0 phase
    while [ "$t" -lt "$2" ]; do
        phase=$(kubectl -n rq2 get pod "$1" -o jsonpath='{.status.phase}' 2>/dev/null)
        [ "$phase" = Succeeded ] && return 0
        [ "$phase" = Failed ] && return 1
        sleep 30; t=$((t + 30)); [ $((t % 300)) = 0 ] && say "$1: still waiting ($phase, ${t}s)"
    done
    return 1
}

pull() {   # <pod> <dir> <instances>: an empty file is a failure (wrong node, no output)
    local i e
    mkdir -p "$2"
    for i in $(seq 0 $(($3 - 1))); do
        for e in csv meta.json; do
            on_node cat "$NODE_DIR/${1}_instance$i.$e" > "$2/instance$i.$e" 2>/dev/null
            [ -s "$2/instance$i.$e" ] || { say "missing or empty on the node: $NODE_DIR/${1}_instance$i.$e"; return 1; }
        done
    done
}

check() {   # <dir> <instances> <jobs>: row count = jobs and the real-time flags of the meta file true
    local i
    for i in $(seq 0 $(($2 - 1))); do
        python3 - "$1/instance$i.csv" "$1/instance$i.meta.json" "$3" <<'PY' || return 1
import json, sys
rows = sum(1 for _ in open(sys.argv[1])) - 1
meta = json.load(open(sys.argv[2]))
bad = [k for k in ("mlockall_ok", "sched_fifo_ok", "affinity_ok") if meta.get(k) is not True]
if rows != int(sys.argv[3]) or bad:
    print("check failed: %s has %d rows (expected %s)%s" % (sys.argv[1], rows, sys.argv[3], ", not true in the meta file: " + ", ".join(bad) if bad else ""))
    sys.exit(1)
PY
    done
}

misses() {   # <dir> <instances>: a first look at the result, for the log (the real analysis is step 5's validate.py)
    python3 - "$1" "$2" <<'PY'
import csv, sys
out = []
for i in range(int(sys.argv[2])):
    rows = list(csv.DictReader(open(f"{sys.argv[1]}/instance{i}.csv")))
    sk = sum(r["skipped"] == "1" for r in rows); late = sum(r["skipped"] == "0" and r["deadline_met"] == "0" for r in rows)
    out.append(f"instance{i}: {late + sk} misses (late {late}, skipped {sk}) of {len(rows)}")
print("; ".join(out))
PY
}

diag() {   # <pod>: state and logs before the pod is deleted
    { echo "--- pod $1 at the failure:"; kubectl -n rq2 get pod "$1" -o wide; kubectl -n rq2 describe pod "$1" | tail -n 12; echo "--- its logs:"; kubectl -n rq2 logs "$1" --tail=15; } 2>&1 | sed 's/^/    /' >> "$LOG"
}

if [ "$DRY_RUN" != 1 ]; then
    left=$(kubectl -n rq2 get pod -l validation=true -o name 2>/dev/null; kubectl -n rq2 get pod rq2-single-instance0 rq2-multi -o name 2>/dev/null)
    [ -z "$left" ] || { echo "pods exist (a running validation, or leftovers): $(echo $left | tr '\n' ' '). Wait for them or delete them first." >&2; exit 1; }
fi
set -m                                           # each scenario in its own process group, so Ctrl-C and `pkill -TERM` can stop them all
trap 'trap "" INT TERM; echo "interrupted: stopping the runs and the enemies"; kill -TERM -- $(jobs -p | sed "s/^/-/") 2>/dev/null; wait; exit 130' INT TERM
for sc in $SCENARIOS; do ( validate_scenario "$sc" ) & done
status=0
for _ in $SCENARIOS; do wait -n || status=1; done
[ $status = 0 ] && echo "online validation: all runs collected. Check them: see README.md (step 5)" || echo "some runs FAILED: see results/<scenario>/validation.log and summary.tsv"
exit $status
