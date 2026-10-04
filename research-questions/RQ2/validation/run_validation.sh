#!/usr/bin/env bash
# run_validation.sh <multi_core|single_core> [route1|route2b|all]        (routes default: all)
#
# Online validation of the budgets under KubeDeadline, unattended. For every run it applies one manifest of
# validation/manifests/<scenario>/<route>/, optionally with the memory enemy running, waits for the pod, pulls the CSV
# and meta.json of every instance from the node (through the node-prep agent, no ssh), checks them, and saves them
# on this machine in validation/results/<scenario>/<route>/<p>_<interference>/.
#
#   multi_core  -> VM rt-k8s-worker-6 (multi-core was profiled on worker7), 2 instances, enemy on cpus 3,0
#   single_core -> VM rt-k8s-worker-7 (single-core was profiled on worker6), 1 instance,  enemy on cpus 2,3,0
#   12 runs for "all": 3 tolerances (p1e-3 first, then p1e-2, p1e-1) x 2 routes x {none, memory}
#   each run is 50000 jobs, ~36 min, so ~7.2 h per scenario (6 runs, ~3.6 h, with route1 or route2b)
#
# The two scenarios run on different VMs, so start them at the same time in two commands:
#   cd research-questions/RQ2
#   setsid nohup validation/run_validation.sh multi_core  > /dev/null 2>&1 < /dev/null &
#   setsid nohup validation/run_validation.sh single_core > /dev/null 2>&1 < /dev/null &
#   tail -f validation/results/multi_core/validation.log        (and single_core)
#
# Safe to repeat: a run that is already collected (results/.../.done) is skipped, so after a crash or a reboot of
# the control plane you just start it again. A run that fails is retried once, then recorded as FAILED and the rest
# goes on (see results/<scenario>/summary.tsv and the end of the log). DRY_RUN=1 prints the plan and touches nothing.
#
# The manifests are pinned to the VM of the scenario. Override with NODE=... NODE_PREP_NS=... only together with
# regenerated manifests (make_manifests.py, SCEN inside). It stops at the start, without doing anything, if: the agent
# of that node is not found, the node lacks the label experiment-model=rq2, an rq2-enemy is already running, or a pod
# of the run already exists.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RQ2_ROOT="$(dirname "$HERE")"
cd "$RQ2_ROOT"

SCEN="${1:-}"
WHICH="${2:-all}"
case "$SCEN" in
    multi_core)
        NODE_DEFAULT=rt-k8s-worker-6; NS_DEFAULT=rq2-node-prep-worker6; ENEMY_CPUS_DEFAULT="3,0"
        INSTANCES=(instance0 instance1) ;;
    single_core)
        NODE_DEFAULT=rt-k8s-worker-7; NS_DEFAULT=rq2-node-prep-worker7; ENEMY_CPUS_DEFAULT="2,3,0"
        INSTANCES=(instance0) ;;
    *) echo "usage: run_validation.sh <multi_core|single_core> [route1|route2b|all]" >&2; exit 2 ;;
esac
case "$WHICH" in
    route1)  ROUTES=(route1) ;;
    route2b) ROUTES=(route2b) ;;
    all)     ROUTES=(route1 route2b) ;;
    *) echo "usage: run_validation.sh <multi_core|single_core> [route1|route2b|all]" >&2; exit 2 ;;
esac

NODE="${NODE:-$NODE_DEFAULT}"
NODE_PREP_NS="${NODE_PREP_NS:-$NS_DEFAULT}"
WORKLOAD_NS="${WORKLOAD_NS:-rq2}"
ENEMY_CPUS="${ENEMY_CPUS:-$ENEMY_CPUS_DEFAULT}"     # the cpus that are not the workload's
MEMORY_SIZE_KB="${MEMORY_SIZE_KB:-2662400}"         # as in workload/run_campaign.sh
STRIDE_BYTES="${STRIDE_BYTES:-64}"
ATTEMPTS="${ATTEMPTS:-2}"
SETTLE_S="${SETTLE_S:-10}"
POLL_S="${POLL_S:-30}"                              # how often the pod phase is read
TIMEOUT_S="${TIMEOUT_S:-6000}"                      # per run; 50000 jobs take about 35 min
HOST_RESULTS="/var/lib/rq2/results/$SCEN"           # hostPath of the pods, read through the agent
TOLS=(p1e-3 p1e-2 p1e-1)
CONDS=(none memory)

RES="$HERE/results/$SCEN"
mkdir -p "$RES"
LOG="$RES/validation.log"
log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }

RUNS=()                                             # "route|ptag|cond|manifest"
for t in "${TOLS[@]}"; do for r in "${ROUTES[@]}"; do for c in "${CONDS[@]}"; do
    m="$HERE/manifests/$SCEN/$r/${t}_${c}.yaml"
    [ -f "$m" ] || { echo "missing manifest: $m (run validation/make_manifests.py)" >&2; exit 1; }
    RUNS+=("$r|$t|$c|$m")
done; done; done

if [ "${DRY_RUN:-0}" = 1 ]; then
    echo "plan: $SCEN, ${#RUNS[@]} runs on $NODE (agent namespace $NODE_PREP_NS), enemy cpus $ENEMY_CPUS for the *_memory runs"
    for e in "${RUNS[@]}"; do
        IFS='|' read -r r t c m <<< "$e"
        printf '  %-8s %-6s %-7s %s | %s\n' "$r" "$t" "$c" "$(sed -n 's/^# id: //p' "$m")" "$(sed -n 's/^# Budget Q\* = //p' "$m" | cut -c1-60)"
    done
    exit 0
fi

# ---------------------------------------------------------------- cluster side
STRESS_DIR="${STRESS_DIR:-}"
if [ -z "$STRESS_DIR" ]; then
    for d in stress1 stress; do
        if [ -f "$RQ2_ROOT/$d/campaign_start_enemies.sh" ]; then STRESS_DIR="$RQ2_ROOT/$d"; break; fi
    done
fi
if [ ! -f "${STRESS_DIR:-/nonexistent}/campaign_start_enemies.sh" ] || [ ! -f "$STRESS_DIR/campaign_stop_enemies.sh" ]; then
    log "FATAL: campaign_start_enemies.sh / campaign_stop_enemies.sh not found (looked in stress1/ and stress/; set STRESS_DIR)"
    exit 1
fi

# the agent ON THE NODE of the scenario (a namespace can hold a second, dead agent, e.g. of a node that is switched off)
AGENT=$(kubectl -n "$NODE_PREP_NS" get pod -l app=rq1-agent --field-selector "spec.nodeName=$NODE" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) || true
[ -n "$AGENT" ] || { log "FATAL: no node-prep agent in $NODE_PREP_NS on node $NODE (is the node Ready and labelled rq2-isolation?)"; exit 1; }
if [ "$(kubectl get node "$NODE" -o jsonpath='{.metadata.labels.experiment-model}')" != "rq2" ]; then
    log "FATAL: node $NODE lacks the label experiment-model=rq2 that the pods select on. Label it yourself: kubectl label node $NODE experiment-model=rq2"
    exit 1
fi
log "validation start: $SCEN, ${#RUNS[@]} runs, node=$NODE agent=$AGENT enemy_cpus=$ENEMY_CPUS stress_dir=$STRESS_DIR"

node_exec() { kubectl -n "$NODE_PREP_NS" exec "$AGENT" -- nsenter --target 1 --mount --pid -- "$@"; }

ENEMIES_UP=0
start_enemies() {
    local result
    log "starting the memory enemy (size=${MEMORY_SIZE_KB}KB stride=$STRIDE_BYTES) on cpus $ENEMY_CPUS"
    ENEMIES_UP=1                                    # from here on the exit trap makes sure they get stopped
    result=$(kubectl -n "$NODE_PREP_NS" exec -i "$AGENT" -- nsenter --target 1 --mount -- \
        bash -s -- "$MEMORY_SIZE_KB" "$STRIDE_BYTES" "$ENEMY_CPUS" < "$STRESS_DIR/campaign_start_enemies.sh" 2>&1) || true
    echo "$result" | tee -a "$LOG"
    if echo "$result" | grep -qE "MISSING|LOW_CPU"; then
        log "FATAL: an enemy failed to start or is not really running - not trusting this run"
        exit 1
    fi
}
stop_enemies() {                                    # returns 1 if an enemy could not be confirmed stopped
    local result
    log "stopping the enemies"
    result=$(kubectl -n "$NODE_PREP_NS" exec -i "$AGENT" -- nsenter --target 1 --mount -- \
        bash -s -- < "$STRESS_DIR/campaign_stop_enemies.sh" 2>&1) || true
    echo "$result" | tee -a "$LOG"
    if echo "$result" | grep -q "STILL_ALIVE_AFTER_SIGKILL"; then
        log "FATAL: could not confirm the enemies stopped even after SIGKILL"
        return 1
    fi
    ENEMIES_UP=0
}
on_exit() {
    if [ "$ENEMIES_UP" = 1 ]; then
        log "exiting while the enemy may still be running - stopping it"
        stop_enemies || log "WARNING: an enemy may still be alive on $NODE - kill the pids in /tmp/rq2_campaign_enemy.pids on the node"
    fi
}
trap on_exit EXIT
trap 'exit 130' INT TERM

preflight() {                                       # $1 = pod name of the run
    local enemies
    enemies=$(node_exec bash -c 'pgrep -x rq2-enemy || true' 2>/dev/null) || true
    if [ -n "$enemies" ]; then
        log "FATAL: rq2-enemy is already running on $NODE (pids: $(echo $enemies)) - the run would not be clean. Stop it first."
        exit 1
    fi
    if kubectl -n "$WORKLOAD_NS" get pod "$1" >/dev/null 2>&1; then
        log "FATAL: pod $WORKLOAD_NS/$1 already exists - delete it (kubectl -n $WORKLOAD_NS delete pod $1) and start again"
        exit 1
    fi
}

cleanup_objects() {                                 # the objects of one run, by name (never the namespace)
    local id="$1"
    kubectl -n "$WORKLOAD_NS" delete pod "$id" --ignore-not-found 2>&1 | tee -a "$LOG" || true
    kubectl -n "$WORKLOAD_NS" delete configmap "$id-config" --ignore-not-found >/dev/null 2>&1 || true   # multi-core only
    kubectl -n "$WORKLOAD_NS" delete resourceclaimtemplate.resource.k8s.io "$id-claim" --ignore-not-found >/dev/null 2>&1 || true
    kubectl -n "$WORKLOAD_NS" delete rtclaimparameters.rt.resource.example.com "$id-params" --ignore-not-found >/dev/null 2>&1 || true
}

# Reads the pod phase every POLL_S seconds. Not kubectl wait: a watch that is closed early makes it return before the
# pod is done (that restarted whole runs before). A few unreadable answers in a row are tolerated.
wait_pod() {
    local pod="$1" waited=0 unreadable=0 phase
    log "waiting for $pod (poll ${POLL_S}s, timeout ${TIMEOUT_S}s)"
    while :; do
        phase=$(kubectl -n "$WORKLOAD_NS" get pod "$pod" -o jsonpath='{.status.phase}' 2>/dev/null) || phase=""
        case "$phase" in
            Succeeded) return 0 ;;
            Failed)    log "pod $pod Failed; last log lines:"; kubectl -n "$WORKLOAD_NS" logs "$pod" --tail=5 2>&1 | tee -a "$LOG" || true; return 1 ;;
            "")        unreadable=$((unreadable + 1))
                       if [ "$unreadable" -ge 20 ]; then log "cannot read the phase of $pod (20 times in a row)"; return 1; fi ;;
            *)         unreadable=0 ;;
        esac
        if [ "$waited" -ge "$TIMEOUT_S" ]; then log "timeout: $pod is still $phase after ${TIMEOUT_S}s"; return 1; fi
        sleep "$POLL_S"; waited=$((waited + POLL_S))
    done
}

pull_run() {                                        # $1 id, $2 out dir
    local inst ext
    for inst in "${INSTANCES[@]}"; do
        for ext in csv meta.json; do
            log "pull ${1}_${inst}.${ext}"
            node_exec cat "$HOST_RESULTS/${1}_${inst}.${ext}" > "$2/${inst}.${ext}" || return 1
            [ -s "$2/${inst}.${ext}" ] || { log "empty file ${inst}.${ext}"; return 1; }
        done
    done
}

check_run() {                                       # $1 out dir, $2 expected jobs: rows, rt flags, jobs in meta.json
    INSTANCES_LIST="${INSTANCES[*]}" python3 - "$1" "$2" <<'EOF'
import json, os, sys
out, jobs = sys.argv[1], int(sys.argv[2])
for inst in os.environ["INSTANCES_LIST"].split():
    rows = sum(1 for _ in open(f"{out}/{inst}.csv")) - 1
    if rows != jobs:
        print(f"CHECK FAILED: {inst}.csv has {rows} rows, expected {jobs}"); sys.exit(1)
    m = json.load(open(f"{out}/{inst}.meta.json"))
    bad = [k for k in ("mlockall_ok", "sched_fifo_ok", "affinity_ok") if m.get(k) is not True]
    if bad:
        print(f"CHECK FAILED: {', '.join(bad)} not true in {inst}.meta.json"); sys.exit(1)
    if m.get("args", {}).get("jobs") != jobs:
        print(f"CHECK FAILED: {inst}.meta.json records jobs={m.get('args', {}).get('jobs')}, expected {jobs}"); sys.exit(1)
EOF
}

quick_stats() {                                     # misses = late (deadline_met == 0) or skipped jobs
    INSTANCES_LIST="${INSTANCES[*]}" python3 - "$1" <<'EOF'
import csv, os, sys
for inst in os.environ["INSTANCES_LIST"].split():
    n = miss = 0
    for r in csv.DictReader(open(f"{sys.argv[1]}/{inst}.csv")):
        if r["warmup"] == "1":
            continue
        n += 1
        miss += (r["skipped"] == "1") or (r["deadline_met"] == "0")
    print(f"  {inst}: {miss} misses in {n} jobs ({miss / n:.2e})")
EOF
}

# ---------------------------------------------------------------- the runs
FAILED=()
run_one() {
    local route="$1" ptag="$2" cond="$3" manifest="$4" id jobs out ok=0 attempt
    id=$(sed -n 's/^# id: //p' "$manifest" | head -1)
    jobs=$(grep -m1 -oE '(--jobs=|"jobs": )[0-9]+' "$manifest" | grep -oE '[0-9]+$')
    [ -n "$id" ] && [ -n "$jobs" ] || { log "FATAL: no '# id:' line or jobs in $manifest"; exit 1; }
    out="$RES/$route/${ptag}_${cond}"
    if [ -f "$out/.done" ]; then log "skip $route/${ptag}_${cond}: already collected"; return 0; fi
    mkdir -p "$out"; cp "$manifest" "$out/manifest.yaml"
    log "=== $SCEN $route $ptag $cond ($id, $jobs jobs per instance) ==="
    preflight "$id"
    if [ "$cond" = memory ]; then start_enemies; fi

    for attempt in $(seq 1 "$ATTEMPTS"); do
        if [ "$attempt" -gt 1 ]; then log "retrying (attempt $attempt/$ATTEMPTS)"; cleanup_objects "$id"; fi
        log "applying $manifest"
        if ! kubectl apply -f "$manifest" 2>&1 | tee -a "$LOG"; then log "kubectl apply failed"; continue; fi
        if wait_pod "$id" && pull_run "$id" "$out" && check_run "$out" "$jobs" 2>&1 | tee -a "$LOG"; then
            ok=1; break
        fi
        log "attempt $attempt/$ATTEMPTS failed"
    done
    cleanup_objects "$id"
    if [ "$cond" = memory ]; then stop_enemies || exit 1; fi    # it must never run into the next run

    if [ "$ok" = 1 ]; then
        touch "$out/.done"
        log "=== $SCEN $route $ptag $cond done ==="
        quick_stats "$out" | tee -a "$LOG"
        printf '%s\t%s\t%s\t%s\tok\n' "$(date -u +%FT%TZ)" "$route" "$ptag" "$cond" >> "$RES/summary.tsv"
    else
        FAILED+=("$route/${ptag}_${cond}")
        log "=== $SCEN $route $ptag $cond FAILED after $ATTEMPTS attempt(s) - data missing or incomplete ==="
        printf '%s\t%s\t%s\t%s\tFAILED\n' "$(date -u +%FT%TZ)" "$route" "$ptag" "$cond" >> "$RES/summary.tsv"
    fi
    sleep "$SETTLE_S"
}

for e in "${RUNS[@]}"; do
    IFS='|' read -r r t c m <<< "$e"
    run_one "$r" "$t" "$c" "$m"
done

echo | tee -a "$LOG"
if [ ${#FAILED[@]} -eq 0 ]; then
    log "validation complete ($SCEN): all ${#RUNS[@]} runs collected in $RES"
else
    log "validation finished ($SCEN) with ${#FAILED[@]} FAILED run(s): ${FAILED[*]} - start the script again to retry only those"
fi
