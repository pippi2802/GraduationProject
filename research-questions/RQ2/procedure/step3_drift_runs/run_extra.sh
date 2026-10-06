#!/usr/bin/env bash
# Step 3: one further run of YOUR workload, on another VM or at another time, to measure how the bound drifts between runs.
# Run it several times (at least two extra baselines are needed; three or more baseline runs in all make alpha_drift meaningful),
# then once for the extra stressed run.
#
#   baseline (label of your choice, e.g. the VM or the day):
#   ./run_extra.sh baseline --label vm2 --scenario single_core --pod-yaml ../../workload/pods/single_core_pod.yaml \
#       --node rt-k8s-worker-7 --agent-ns rq2-node-prep-worker7 --node-dir /var/lib/rq2/results/single_core --prefix single_core --instances 1
#   stressed run, paired with the baseline that was measured next to it (same node, close in time):
#   ./run_extra.sh stress --paired-with vm2 --scenario single_core ... --enemy-cpus 2,3,0 [--enemy memory|cache]
#
#   results: results/<scenario>/extra_baselines/<label>/instance<N>.csv     and     results/<scenario>/stress_run/instance<N>.csv
#   The arguments are those of step 2 (see ../step2_profiling/run_profiling.sh), with the YAML of the SAME workload as in step 2.
#   --paired-with  (stress) the label of the baseline measured next to it; step 4 uses it for the stress ratio on that run and the rule for m
#   --enemy        (stress) memory (default) or cache
#
# The workload contract (any workload that follows it works):
#   - a pod YAML with ONE Pod, whose nodeSelector is a one-line flow mapping ("nodeSelector: { key: value }"); this script adds the node.
#   - the pod writes /results/<prefix>_instance<N>.csv and .meta.json (N = 0, 1, ...) to a hostPath directory of the node (--node-dir).
#   - the CSV has the columns job_id, skipped, warmup, cpu_ns, release_ns, response_ns (more is welcome: see step 4's README).
#   - the number of jobs of a run is set in the pod YAML (edit it there).
# Prerequisites: kubectl on this machine; a node-prep agent pod (label app=rq1-agent) in --agent-ns on that node, as in setup/;
# the enemy binary installed on the node as /usr/local/bin/rq2-enemy (./install_enemy.sh in step 2).
set -uo pipefail

SCENARIO="" POD_YAML="" NODE="" AGENT_NS="" NODE_DIR="" PREFIX="" INSTANCES=1 ENEMY_CPUS=""
CACHE_KB=266240 MEMORY_KB=2662400 STRIDE=64 TIMEOUT_S=7200 ATTEMPTS=2 SETTLE_S=10

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
usage() { sed -n '2,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'; }
say() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die() { echo "error: $*" >&2; exit 2; }

setup() {
    for v in SCENARIO POD_YAML NODE AGENT_NS NODE_DIR PREFIX ENEMY_CPUS; do [ -n "${!v}" ] || die "missing --$(echo "$v" | tr 'A-Z_' 'a-z-') (run without arguments for the usage)"; done
    [ -f "$POD_YAML" ] || die "pod yaml not found: $POD_YAML"
    [ "$(grep -c '^[[:space:]]*nodeSelector:' "$POD_YAML")" = 1 ] || die "$POD_YAML must have exactly one nodeSelector line"
    grep -qE '^[[:space:]]*nodeSelector:[[:space:]]*\{.*\}[[:space:]]*$' "$POD_YAML" || die "the nodeSelector of $POD_YAML must be a one-line flow mapping: nodeSelector: { key: value }"
    AGENT=$(kubectl -n "$AGENT_NS" get pod -l app=rq1-agent --field-selector "spec.nodeName=$NODE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    [ -n "$AGENT" ] || die "no node-prep agent (label app=rq1-agent) on node $NODE in namespace $AGENT_NS"
    HOST=$(kubectl get node "$NODE" -o jsonpath='{.metadata.labels.kubernetes\.io/hostname}')
    [ -n "$HOST" ] || die "node $NODE not found"
    read -r POD_NS POD < <(kubectl apply --dry-run=client -f "$POD_YAML" -o json | python3 -c '
import json, sys
d = json.load(sys.stdin)
for o in (d["items"] if d.get("kind") == "List" else [d]):
    if o["kind"] == "Pod":
        print(o["metadata"].get("namespace", "default"), o["metadata"]["name"])')
    [ -n "${POD:-}" ] || die "no Pod found in $POD_YAML"
    if kubectl -n "$POD_NS" get pod "$POD" > /dev/null 2>&1; then die "pod $POD_NS/$POD already exists: wait for it or kubectl -n $POD_NS delete pod $POD"; fi
    PINNED="$(mktemp)"
    sed -E "s#^([[:space:]]*nodeSelector:.*[^[:space:]])[[:space:]]*\}[[:space:]]*\$#\1, kubernetes.io/hostname: $HOST }#" "$POD_YAML" > "$PINNED"
    grep -q "kubernetes.io/hostname: $HOST" "$PINNED" || die "could not pin the pod to $HOST"
    trap 'stop_enemies' EXIT; trap 'exit 130' INT TERM       # whatever happens, no enemy is left running
    stop_enemies                                              # clean start
    no_strays "at the start"
    say "node $NODE (agent $AGENT), pod $POD_NS/$POD, $INSTANCES instance(s), enemy cpus $ENEMY_CPUS"
}

on_node() { kubectl -n "$AGENT_NS" exec -i "$AGENT" -- nsenter --target 1 --mount -- "$@"; }

start_enemies() {   # <size KB>: starts one enemy per cpu and CONFIRMS each really burns cpu
    local out
    out=$(on_node bash -s -- "$1" "$STRIDE" "$ENEMY_CPUS" < "$HERE/campaign_start_enemies.sh" 2>&1)
    echo "$out" | sed 's/^/    /'
    if echo "$out" | grep -qE "MISSING|LOW_CPU"; then say "FATAL: an enemy is not running; install it first (step 2: ./install_enemy.sh)"; stop_enemies; exit 1; fi
}

strays() { on_node pgrep -x rq2-enemy > /dev/null 2>&1; }     # 0 when an enemy is running, BY NAME: the stop script only knows its own pidfile

no_strays() {       # <when>: an enemy this script did not start would contaminate the data of the run
    if strays; then
        say "FATAL: an rq2-enemy is running on $NODE that this script did not start ($1): the data would be contaminated"
        on_node ps -o pid,lstart,psr,pcpu,args -C rq2-enemy 2>&1 | sed 's/^/    /'
        say "if nothing else uses $NODE, stop it: kubectl -n $AGENT_NS exec -i $AGENT -- nsenter --target 1 --mount --pid -- pkill -x rq2-enemy"
        exit 1
    fi
}

stop_enemies() {    # SIGTERM, polled until gone, SIGKILL after a grace period
    local out
    out=$(on_node bash -s -- < "$HERE/campaign_stop_enemies.sh" 2>&1) || true
    echo "$out" | grep -q STILL_ALIVE && { say "FATAL: an enemy could not be stopped on $NODE"; exit 1; }
    return 0
}

wait_pod() {        # 0 when the pod Succeeded; 1 when it Failed or the timeout passed (a failed pod is seen at once)
    local t=0 phase
    while [ "$t" -lt "$TIMEOUT_S" ]; do
        phase=$(kubectl -n "$POD_NS" get pod "$POD" -o jsonpath='{.status.phase}' 2>/dev/null)
        [ "$phase" = Succeeded ] && return 0
        [ "$phase" = Failed ] && return 1
        sleep 5; t=$((t + 5))
    done
    return 1
}

pull() {            # <out dir>: every instance's csv + meta from the node; an empty file is a failure (wrong node, no output)
    local out="$1" i ext
    mkdir -p "$out"
    for i in $(seq 0 $((INSTANCES - 1))); do
        for ext in csv meta.json; do
            on_node cat "$NODE_DIR/${PREFIX}_instance$i.$ext" > "$out/instance$i.$ext" 2>/dev/null
            [ -s "$out/instance$i.$ext" ] || { say "missing or empty on the node: $NODE_DIR/${PREFIX}_instance$i.$ext"; return 1; }
        done
    done
}

check() {           # <out dir>: rows in every csv, and the real-time flags of the meta file when it has them
    local out="$1" i
    for i in $(seq 0 $((INSTANCES - 1))); do
        python3 - "$out/instance$i.csv" "$out/instance$i.meta.json" <<'PY' || return 1
import json, sys
rows = sum(1 for _ in open(sys.argv[1])) - 1
meta = json.load(open(sys.argv[2]))
bad = [k for k in ("mlockall_ok", "sched_fifo_ok", "affinity_ok") if k in meta and meta[k] is not True]
if rows < 1000 or bad:
    print("check failed: %s has %d rows%s" % (sys.argv[1], rows, ", not true in the meta file: " + ", ".join(bad) if bad else ""))
    sys.exit(1)
PY
    done
}

diag() {            # pod state and logs, before the pod is deleted
    { echo "--- pod $POD at the failure:"; kubectl -n "$POD_NS" get pod "$POD" -o wide
      kubectl -n "$POD_NS" describe pod "$POD" | tail -n 12; echo "--- its logs:"; kubectl -n "$POD_NS" logs "$POD" --tail=15; } 2>&1 | sed 's/^/    /'
}

run_one() {         # <name> <out dir> <enemy size KB or empty>
    local name="$1" out="$2" kb="$3" try ok=0
    say "=== $name"
    no_strays "before $name"
    [ -n "$kb" ] && start_enemies "$kb"
    for try in $(seq 1 "$ATTEMPTS"); do
        kubectl -n "$POD_NS" delete pod "$POD" --ignore-not-found > /dev/null 2>&1
        kubectl apply -f "$PINNED" > /dev/null && wait_pod && pull "$out" && check "$out" && { ok=1; break; }
        say "attempt $try failed"; diag
    done
    kubectl -n "$POD_NS" delete pod "$POD" --ignore-not-found > /dev/null 2>&1
    [ -n "$kb" ] && stop_enemies
    no_strays "after $name"
    if [ "$ok" = 1 ]; then say "$name done -> $out"; else say "$name FAILED"; FAILED+=("$name"); fi
    sleep "$SETTLE_S"
}
FAILED=()

KIND="${1:-}"; shift || true
LABEL="" PAIRED="" ENEMY=memory OUT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --scenario) SCENARIO="$2"; shift 2 ;; --pod-yaml) POD_YAML="$2"; shift 2 ;; --node) NODE="$2"; shift 2 ;;
        --agent-ns) AGENT_NS="$2"; shift 2 ;; --node-dir) NODE_DIR="$2"; shift 2 ;; --prefix) PREFIX="$2"; shift 2 ;;
        --instances) INSTANCES="$2"; shift 2 ;; --enemy-cpus) ENEMY_CPUS="$2"; shift 2 ;; --cache-kb) CACHE_KB="$2"; shift 2 ;;
        --memory-kb) MEMORY_KB="$2"; shift 2 ;; --timeout-s) TIMEOUT_S="$2"; shift 2 ;; --attempts) ATTEMPTS="$2"; shift 2 ;; --settle-s) SETTLE_S="$2"; shift 2 ;;
        --label) LABEL="$2"; shift 2 ;; --paired-with) PAIRED="$2"; shift 2 ;; --enemy) ENEMY="$2"; shift 2 ;; --out) OUT="$2"; shift 2 ;;
        *) usage; exit 2 ;;
    esac
done
case "$KIND" in
    baseline) [ -n "$LABEL" ] || die "baseline needs --label"; [ -n "$ENEMY_CPUS" ] || ENEMY_CPUS=none; DEST="extra_baselines/$LABEL"; KB="" ;;
    stress)   [ -n "$PAIRED" ] || die "stress needs --paired-with <label of the baseline measured next to it>"; DEST="stress_run"
              case "$ENEMY" in memory) KB="$MEMORY_KB" ;; cache) KB="$CACHE_KB" ;; *) die "--enemy is memory or cache" ;; esac ;;
    *) usage; exit 2 ;;
esac
[ -n "$SCENARIO" ] || { usage; exit 2; }
OUT="${OUT:-$HERE/results/$SCENARIO}"
[ "$KIND" = stress ] && [ ! -d "$OUT/extra_baselines/$PAIRED" ] && say "warning: no baseline '$PAIRED' in $OUT/extra_baselines yet (run it, or the pairing will not resolve in step 4)"
setup
run_one "$KIND${LABEL:+ $LABEL}${PAIRED:+ (paired with $PAIRED)}" "$OUT/$DEST" "$KB"
if [ ${#FAILED[@]} -eq 0 ]; then
    [ "$KIND" = stress ] && echo "$PAIRED" > "$OUT/stress_run/paired_with.txt"
    say "done: $OUT/$DEST"
else
    exit 1
fi
