#!/usr/bin/env bash
# run_job.sh <model> [soft|tight] — run the generated sweep, one cell at a time.
#
# Ported near-verbatim from RQ1/run_job.sh (already properly generic --
# parameterized by <model>, reads co_runners/target_threads from each
# model's own config.yaml rather than being hardcoded to one model). This
# replaces the earlier model1-only trimmed version RQ1_final started with.
#
# RQ1_final only ever runs one workload (workload.c's sieve, not matmul's
# multi-kind matmul/primes split) -- the WORKLOAD/WORKLOAD_KIND machinery
# below is left in unchanged from RQ1's version because leaving WORKLOAD
# unset here naturally resolves to its "matmul" default branch, which is
# exactly RQ1_final's own naming convention (k_table.json under
# models/<model>/, generated/ not generated_<kind>/) -- do not set WORKLOAD
# when invoking this for RQ1_final, there is nothing to select between.
#
# Two harmless-if-missing references, both opt-in / informational only:
#   - node-prep/steer-irqs.sh (IRQ_STEER arm) -- only reached if IRQ_STEER
#     is explicitly set; RQ1_final's own node-prep/harden-core.sh's
#     irq-steer action is a different, always-on mechanism, not this
#     opt-in per-cell arm. Port RQ1's steer-irqs.sh here first if that
#     specific per-cell A/B arm is ever wanted.
#   - result.py, in the final hint line only -- not required to run the sweep.
#
# Every cell is validated before it's accepted (see CELL_ATTEMPTS below): a
# bad calibration, a placement that didn't land where the model requires, or a
# short jobs.csv all trigger an automatic retry instead of silently recording
# bad data. Cells that still fail after retrying are listed in the final
# summary -- check that list before trusting a sweep's results.
set -uo pipefail
MODEL="${1:?usage: run_job.sh <model> [soft|tight]}"
SCALE="${2:-}"
cd "$(dirname "$0")"

# --- model3 placement knobs --------------------------------------------------
# model3 only: how the target is placed relative to the (fixed-intensity)
# competitor. The competitor's own utilization never changes across the U
# sweep (co_runners.competitor.u), so it's created ONCE per scale (see
# place_fixed_competitor below) and left running for every cell of that
# scale -- the target (count:1, same as model1's own claim) is then forced
# onto a cpu computed once, relative to the competitor's actual landed cpu --
#   sibling  -> target's cpu is the competitor's SMT sibling (same physical
#               core)                                              [default]
#   physical -> target's cpu is on a DIFFERENT physical core than the
#               competitor
PAIR_TYPE="${PAIR_TYPE:-sibling}"
# model3 only: what the competitor actually is --
#   unreserved -> CFS sieve, taskset-pinned to a cpu WE choose directly (it
#                 never goes through the driver)                    [default]
#   reserved   -> its own CBS reservation (co_runners.competitor.u); its cpu
#                 is the driver's own (uncontrollable) choice, read back once
#                 and used to compute the target's forced cpu
COMPETITOR_TYPE="${COMPETITOR_TYPE:-unreserved}"
# the one cpu isolate.sh deliberately leaves OUTSIDE isolcpus/nohz_full/
# rcu_nocbs, for kubelet/sshd/general OS housekeeping (isolate.sh's own
# keep_cpu default). Never place the competitor OR the target here, and never
# there for either's SMT sibling either -- anything sharing a physical core
# with keep_cpu picks up whatever uncontrolled housekeeping/interrupt traffic
# lands there, on top of (and confounded with) the intended experimental
# contention. place_fixed_competitor enforces this for both COMPETITOR_TYPEs.
KEEP_CPU="${KEEP_CPU:-0}"
# suffix for the results dir so an arm doesn't overwrite another, e.g.
# OUT_TAG=_phys_res -> results/model3_phys_res/...
OUT_TAG="${OUT_TAG:-}"
# IRQ steering arm (opt-in, needs node-prep/steer-irqs.sh ported first --
# see header note): unset | off | on.
IRQ_STEER="${IRQ_STEER:-}"
# pin the target's FIRST cpu to a specific logical cpu for stable, comparable
# placement. The SMT-blind driver has no core knob, so we delete+recreate until
# worst-fit lands there (up to PIN_ATTEMPTS). Empty = accept whatever it picks.
PIN_RTCPU="${PIN_RTCPU:-}"
PIN_ATTEMPTS="${PIN_ATTEMPTS:-8}"
# how many times to redo a whole cell (placement + competitor landing + run +
# row-count) before giving up and recording it as FAILED.
CELL_ATTEMPTS="${CELL_ATTEMPTS:-4}"
# calibration gate: refuse to run a cell whose recorded calibration cv is above
# this (mis-calibrated K / genuinely broken measurement). See RQ1's own
# memory/rq1_calibration_noise_floor.md for why this isn't 0 -- short-duration
# cells have an intrinsic noise floor even with everything else controlled.
CV_THRESHOLD="${CV_THRESHOLD:-0.05}"
WORKLOAD_KIND="${WORKLOAD:-matmul}"
TAB_NAME="k_table.json"; [ "$WORKLOAD_KIND" != "matmul" ] && TAB_NAME="k_table.$WORKLOAD_KIND.json"
GEN_DIR="generated"; [ "$WORKLOAD_KIND" != "matmul" ] && GEN_DIR="generated_$WORKLOAD_KIND"

read -r NS HOST_PATH HAS_NB HAS_COMP MT_THREADS < <(python3 - "$MODEL" <<'PY'
import sys, yaml
c = yaml.safe_load(open(f"models/{sys.argv[1]}/config.yaml"))
cr = c.get("co_runners") or {}
print(c["namespace"], c["host_path"],
      int(bool(cr.get("neighbours"))),
      int("interferer" in cr or "competitor" in cr),
      int(c.get("target_threads") or 0))
PY
)
AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no node agent; run node-prep/apply.sh $MODEL"; exit 1; }

GLOB="models/$MODEL/$GEN_DIR/${SCALE:+$SCALE/}"
[ -n "$SCALE" ] && GLOB="models/$MODEL/$GEN_DIR/$SCALE" || GLOB="models/$MODEL/$GEN_DIR"
mapfile -t FILES < <(find "$GLOB" -name 'U*.yaml' -not -path '*/_intf/*' -not -path '*/_comp/*' -not -path '*/_nb/*' | sort)
[ ${#FILES[@]} -eq 0 ] && { echo "ERROR: no manifests; run generate_yaml.py $MODEL"; exit 1; }

# U_MIN/U_MAX: restrict which cells run instead of the whole sweep. U_MAX skips
# cells above a utilization cap (e.g. model3 sibling arms' shared-core
# ceiling, where anything beyond it is genuinely infeasible and would just
# burn CELL_ATTEMPTS*PIN_ATTEMPTS retries for nothing). U_MIN=U_MAX=<value>
# isolates exactly one cell -- useful for manually re-running a single cell
# that failed a prior sweep without re-running everything else.
if [ -n "${U_MIN:-}${U_MAX:-}" ]; then
  keep=()
  for f in "${FILES[@]}"; do
    u="$(basename "$f" .yaml)"; u="${u#U}"
    awk -v u="$u" -v lo="${U_MIN:--999}" -v hi="${U_MAX:-999}" 'BEGIN{exit !(u+0>=lo+0 && u+0<=hi+0)}' && keep+=("$f")
  done
  FILES=("${keep[@]}")
  echo "[run] U_MIN=${U_MIN:-} U_MAX=${U_MAX:-} applied: ${#FILES[@]} cells remain"
fi
echo "[run] model=$MODEL ns=$NS agent=$AGENT cells=${#FILES[@]} has_neighbours=$HAS_NB has_competitor=$HAS_COMP"
echo "[run] *** WORKLOAD=$WORKLOAD_KIND (GEN_DIR=$GEN_DIR, k_table=$TAB_NAME) -- confirm this is what you meant to run ***"
[ "$HAS_COMP" = 1 ] && echo "[run] model3 arm: PAIR_TYPE=$PAIR_TYPE COMPETITOR_TYPE=$COMPETITOR_TYPE"
[ "$MT_THREADS" -gt 1 ] 2>/dev/null && echo "[run] target_threads=$MT_THREADS, forcing the claimed pair onto two DISTINCT PHYSICAL cores"

# "0-3"/"0,2" -> "0 1 2 3" / "0 2" -- hyphen here is the driver's plain
# delimiter (see RT_CPUSET normalization in every job.yaml), never a range.
expand_cpuset() {
  echo "$1" | tr ',-' '\n\n' | while read -r p; do
    case "$p" in "") ;; *) echo "$p" ;; esac
  done | tr '\n' ' '
}
# space-separated sibling set (includes the cpu itself) for a given logical cpu
siblings_of() {
  local raw
  raw=$(kubectl -n "$NS" exec "$AGENT" -- cat "/sys/devices/system/cpu/cpu$1/topology/thread_siblings_list" 2>/dev/null)
  expand_cpuset "$(echo "$raw" | tr ',-' '  ')"
}
# every logical cpu id present on the node, one per line
all_cpus() {
  kubectl -n "$NS" exec "$AGENT" -- sh -c 'for d in /sys/devices/system/cpu/cpu[0-9]*; do basename "$d"; done' \
    2>/dev/null | sed 's/^cpu//'
}

# the target cpu(s) implied by PAIR_TYPE for a given candidate competitor
# cpu. PAIR_TYPE=sibling has exactly one valid answer (the unique SMT
# sibling); PAIR_TYPE=physical can have MANY (any cpu that isn't the
# candidate or its sibling) -- so this returns a space-separated LIST in
# that case, not just the first one found. Empty output means no valid
# target cpu exists at all (e.g. PAIR_TYPE=sibling on a cpu with no SMT
# sibling). Does NOT know about KEEP_CPU -- callers filter that out
# themselves (filter_keep_cpu below).
target_cpu_for() {
  local candidate="$1"
  case "$PAIR_TYPE" in
    sibling)
      siblings_of "$candidate" | tr ' ' '\n' | grep -vx "$candidate" | head -1
      ;;
    physical)
      local excl=" $(siblings_of "$candidate") $candidate " c out=""
      for c in $(all_cpus | sort -n); do
        case "$excl" in *" $c "*) ;; *) out="$out $c" ;; esac
      done
      echo "${out# }"
      ;;
  esac
}
# remove KEEP_CPU from a (possibly multi-value, space-separated) candidate
# list -- e.g. filter_keep_cpu "0 2 3" -> "2 3".
filter_keep_cpu() {
  echo "$1" | tr ' ' '\n' | grep -vx "$KEEP_CPU" | grep -v '^$' | tr '\n' ' ' | sed 's/ *$//'
}

# `kubectl delete -f <manifest>` parses the RAW file from disk -- unlike
# create (piped through sed to fill @@REQUESTED_CPUS@@/@@INTF_CPU@@ first), a
# bare delete -f reads the literal, never-substituted placeholder, which
# isn't valid YAML, so it silently deletes nothing. Fixed placeholder value
# here since a delete only needs kind/name/namespace, never the real
# contents.
delete_manifest() {
  sed -e 's/@@REQUESTED_CPUS@@/0/g' -e 's/@@INTF_CPU@@/0/g' "$1" | \
    kubectl delete -f - --ignore-not-found --wait=true >/dev/null 2>&1
}

# `kubectl delete -f ... --wait=true` was found (under concurrent load) to
# sometimes return before EVERY object it deletes is actually gone. Polls
# with `kubectl get -f` against the SAME manifest, which checks every object
# it declares (params + claim template + pod) in one call, not just the pod.
wait_manifest_gone() {
  local file="$1" i
  for i in $(seq 1 15); do
    [ -z "$(kubectl get -f "$file" -o name 2>/dev/null)" ] && return 0
    sleep 1
  done
  return 1
}

# wait_manifest_gone only confirms the pod/claim OBJECTS are gone from the
# Kubernetes API -- that is NOT the same moment the cpu is actually released
# by the driver (NodeUnprepareResources is a later, separate node-level
# step). A retry can therefore see "object gone" and request the same cpu
# again while the driver still considers it committed. This polls the
# driver's own bookkeeping directly (NodeAllocationState, namespace
# dra-rt-driver). NODE_NAME is resolved once and cached (matches this
# model's fixed nodeSelector, "experiment-model=<model>").
wait_cpu_free() {
  local cpu="$1" i util
  : "${NODE_NAME:=$(kubectl get nodes -l "experiment-model=$MODEL" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)}"
  [ -z "$NODE_NAME" ] && return 0   # couldn't resolve node -- don't block on this alone
  for i in $(seq 1 20); do
    util=$(kubectl -n dra-rt-driver get nodeallocationstates "$NODE_NAME" \
             -o jsonpath="{.spec.allocatedUtilToCpu.cpus['$cpu'].util}" 2>/dev/null)
    { [ -z "$util" ] || [ "$util" = "0" ]; } && return 0
    sleep 1
  done
  return 1
}
wait_cpus_free() {
  local c
  for c in $(echo "$1" | tr ',' ' '); do
    wait_cpu_free "$c"
  done
}

# Deterministically pick a fixed cpu (avoiding KEEP_CPU) that also has a
# valid PAIR_TYPE-relative pair partner (also avoiding KEEP_CPU). Topology
# never changes cell to cell, so this always returns the same answer -- used
# as a requestedCpus HINT so the driver lands the competitor there on the
# first attempt instead of worst-fit + delete/recreate-until-landed. Empty
# output means no valid cpu exists at all on this node for the current
# PAIR_TYPE.
pick_paired_cpu() {
  local c candidate_target
  for c in $(all_cpus | sort -n); do
    [ "$c" = "$KEEP_CPU" ] && continue
    candidate_target=$(filter_keep_cpu "$(target_cpu_for "$c")")
    if [ -n "$candidate_target" ]; then
      echo "$c"; return 0
    fi
  done
  return 1
}

# `kubectl wait --for=condition=Ready` only proves the container process
# STARTED -- not that it actually holds real RT bandwidth yet (the per-pod
# leaf cgroup rt_runtime is grown on demand under the shared kubepods.slice
# cap). Confirms real execution by sampling the pod's pid-1 utime+stime
# twice, a few seconds apart, and checking it actually advanced.
confirm_burning_cpu() {
  local pod="$1" t0 t1
  t0=$(kubectl -n "$NS" exec "$pod" -- awk '{print $14+$15}' /proc/1/stat 2>/dev/null) || return 1
  [ -n "$t0" ] || return 1
  sleep 3
  t1=$(kubectl -n "$NS" exec "$pod" -- awk '{print $14+$15}' /proc/1/stat 2>/dev/null) || return 1
  [ -n "$t1" ] || return 1
  [ "$t1" -gt "$t0" ] 2>/dev/null
}

# Single-sample cputime read (utime+stime, clock ticks), no internal sleep --
# cheap enough to call every poll iteration of the mid-run watch loop; the
# caller compares consecutive samples itself to detect a stall.
pod_cputime() {
  kubectl -n "$NS" exec "$1" -- awk '{print $14+$15}' /proc/1/stat 2>/dev/null
}

# A QoS slice's cpu.rt_period_us is ONE shared, file-wide value for the WHOLE
# QoS class on that node -- not per-cell, not per-model. Once ANY pod is
# admitted at a given period, that period sticks; a later pod requesting a
# DIFFERENT period collides with it. This resets it automatically, once per
# scale, before anything for that scale is created.
QOS_SLICE="${QOS_SLICE:-kubepods-besteffort.slice}"
QOS_CG="/sys/fs/cgroup/kubepods.slice/$QOS_SLICE"
ensure_qos_period() {
  local want="$1" cur alive
  cur=$(kubectl -n "$NS" exec "$AGENT" -- cat "$QOS_CG/cpu.rt_period_us" 2>/dev/null)
  [ "$cur" = "$want" ] && return 0
  alive=$(kubectl -n "$NS" get pods --no-headers 2>/dev/null | grep -v "^rq1-agent" | grep -v '\bCompleted\b' | wc -l)
  if [ "${alive:-0}" -gt 0 ]; then
    echo "[run] WARNING $QOS_SLICE period is ${cur:-unreadable}, need $want, but $alive pod(s) still alive in $NS -- not resetting (previous teardown may still be in flight); this scale may fail admission"
    return 1
  fi
  echo "[run] $QOS_SLICE period mismatch (have ${cur:-unreadable}, need $want) -- resetting"
  kubectl -n "$NS" exec "$AGENT" -- sh -c "echo '0 0 0 0' > $QOS_CG/cpu.rt_runtime_us" 2>&1 | sed 's/^/[run] /'
  kubectl -n "$NS" exec "$AGENT" -- sh -c "echo $want > $QOS_CG/cpu.rt_period_us" 2>&1 | sed 's/^/[run] /'
  local newcur
  newcur=$(kubectl -n "$NS" exec "$AGENT" -- cat "$QOS_CG/cpu.rt_period_us" 2>/dev/null)
  if [ "$newcur" != "$want" ]; then
    echo "[run] WARNING $QOS_SLICE period still $newcur after reset attempt -- something else may be live on this node; cells on this scale may fail"
    return 1
  fi
  echo "[run] $QOS_SLICE period now $newcur, runtime cleared"
}

# --- model3: place the (fixed-intensity) competitor/interferer ONCE for a
# whole scale, and compute the target's forced cpu relative to it. Sets the
# globals desired_target_cpu, comp_cpu, FIXED_COMP_FILE (empty for the
# unreserved arm, which has no separate claim objects to clean up). Neither
# comp_cpu nor desired_target_cpu is ever allowed to be KEEP_CPU. Returns 1
# if the competitor never came up or no such cpu pair could be found/landed.
place_fixed_competitor() {
  local scale="$1" first_ul="$2"
  desired_target_cpu=""; comp_cpu=""; FIXED_COMP_FILE=""; FIXED_INTF_FILE=""
  [ "$HAS_COMP" != 1 ] && return 0

  if [ "$COMPETITOR_TYPE" = "unreserved" ]; then
    local intf="models/$MODEL/$GEN_DIR/_intf/$scale/$first_ul.yaml"
    FIXED_INTF_FILE="$intf"
    [ -f "$intf" ] || { echo "[run] ERROR _intf manifest missing for $scale"; return 1; }
    comp_cpu=$(pick_paired_cpu) || comp_cpu=""
    [ -n "$comp_cpu" ] && desired_target_cpu=$(filter_keep_cpu "$(target_cpu_for "$comp_cpu")")
    if [ -z "$comp_cpu" ]; then
      echo "[run] ERROR no (competitor,target) cpu pair avoiding KEEP_CPU=$KEEP_CPU for PAIR_TYPE=$PAIR_TYPE"
      return 1
    fi
    local intf_ok=0 intf_attempt intf_pod
    for intf_attempt in 1 2 3 4 5; do
      kubectl -n "$NS" delete pod -l "app=$MODEL,role=interferer" --ignore-not-found --wait=true >/dev/null 2>&1
      sed "s/@@INTF_CPU@@/$comp_cpu/g" "$intf" | kubectl create -f - >/dev/null 2>&1
      if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=interferer" \
            --for=condition=Ready --timeout=150s >/dev/null 2>&1; then
        echo "[run] unreserved competitor pod not Ready ($scale, attempt $intf_attempt/5); retrying"; continue
      fi
      intf_pod=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=interferer" -o jsonpath='{.items[0].metadata.name}')
      if ! confirm_burning_cpu "$intf_pod"; then
        echo "[run] unreserved competitor on cpu$comp_cpu is Ready but not consuming CPU ($scale, attempt $intf_attempt/5); retrying"; continue
      fi
      intf_ok=1; break
    done
    if [ "$intf_ok" != 1 ]; then
      echo "[run] ERROR unreserved competitor never came up actually running for $scale after 5 attempts"
      kubectl -n "$NS" delete pod -l "app=$MODEL,role=interferer" --ignore-not-found >/dev/null 2>&1
      return 1
    fi
    echo "[run] $scale: unreserved competitor fixed on cpu$comp_cpu (avoiding KEEP_CPU=$KEEP_CPU), confirmed actually executing, running for the whole scale"
  elif [ "$COMPETITOR_TYPE" = "reserved" ]; then
    FIXED_COMP_FILE="models/$MODEL/$GEN_DIR/_comp/$scale/$first_ul.yaml"
    [ -f "$FIXED_COMP_FILE" ] || { echo "[run] ERROR _comp manifest missing for $scale"; return 1; }
    kubectl -n "$NS" delete pod -l "app=$MODEL,role=competitor" --ignore-not-found --wait=true >/dev/null 2>&1
    local hint_cpu; hint_cpu=$(pick_paired_cpu) || hint_cpu=""
    if [ -z "$hint_cpu" ]; then
      echo "[run] ERROR no (competitor,target) cpu pair avoiding KEEP_CPU=$KEEP_CPU for PAIR_TYPE=$PAIR_TYPE"
      return 1
    fi
    local ok=0 attempt comp_pod landed candidate_target
    for attempt in 1 2 3 4 5; do
      delete_manifest "$FIXED_COMP_FILE"
      wait_manifest_gone "$FIXED_COMP_FILE"
      wait_cpus_free "$hint_cpu"
      sed "s/@@REQUESTED_CPUS@@/$hint_cpu/g" "$FIXED_COMP_FILE" | kubectl create -f - >/dev/null 2>&1
      if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=competitor" \
            --for=condition=Ready --timeout=150s >/dev/null 2>&1; then
        echo "[run] reserved competitor pod not Ready ($scale, attempt $attempt/5); retrying"; continue
      fi
      comp_pod=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=competitor" -o jsonpath='{.items[0].metadata.name}')
      landed=$(kubectl -n "$NS" exec "$comp_pod" -- printenv RT_CPUSET 2>/dev/null | cut -d, -f1 | cut -d- -f1)
      if [ "$landed" != "$hint_cpu" ]; then
        echo "[run] reserved competitor landed on cpu$landed, wanted cpu$hint_cpu ($scale, attempt $attempt/5); re-placing"; continue
      fi
      candidate_target=$(filter_keep_cpu "$(target_cpu_for "$landed")")
      if [ -z "$candidate_target" ]; then
        echo "[run] reserved competitor on cpu$landed has no usable pair avoiding KEEP_CPU=$KEEP_CPU ($scale, attempt $attempt/5); re-placing"; continue
      fi
      if ! confirm_burning_cpu "$comp_pod"; then
        echo "[run] reserved competitor on cpu$landed is Ready but not consuming CPU (RT budget grant still incomplete?) ($scale, attempt $attempt/5); re-placing"; continue
      fi
      comp_cpu="$landed"; desired_target_cpu="$candidate_target"; ok=1; break
    done
    if [ "$ok" != 1 ]; then
      echo "[run] ERROR reserved competitor never landed on a usable, actually-running cpu (avoiding KEEP_CPU=$KEEP_CPU) for $scale after 5 attempts"
      delete_manifest "$FIXED_COMP_FILE"
      return 1
    fi
    echo "[run] $scale: reserved competitor landed on cpu$comp_cpu (avoiding KEEP_CPU=$KEEP_CPU), confirmed actually executing, running for the whole scale"
  fi

  echo "[run] $scale: target will be forced onto {$desired_target_cpu} for every cell (PAIR_TYPE=$PAIR_TYPE vs competitor cpu$comp_cpu)"
}

# The competitor/interferer has been observed (on RQ1) to exit on its own
# after a sustained run, well before a scale's full sweep is done. Rather
# than silently losing contention for the rest of the scale, run_one_cell's
# wait-loop polls for this and calls this to bring it back.
restart_fixed_competitor() {
  [ "$HAS_COMP" != 1 ] && return 0
  if [ "$COMPETITOR_TYPE" = "unreserved" ]; then
    local attempt intf_pod
    for attempt in 1 2 3; do
      kubectl -n "$NS" delete pod -l "app=$MODEL,role=interferer" --ignore-not-found --wait=true >/dev/null 2>&1
      sed "s/@@INTF_CPU@@/$comp_cpu/g" "$FIXED_INTF_FILE" | kubectl create -f - >/dev/null 2>&1
      if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=interferer" \
            --for=condition=Ready --timeout=150s >/dev/null 2>&1; then
        echo "[run] restart attempt $attempt/3 not Ready; retrying"; continue
      fi
      intf_pod=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=interferer" -o jsonpath='{.items[0].metadata.name}')
      if ! confirm_burning_cpu "$intf_pod"; then
        echo "[run] competitor restarted on cpu$comp_cpu but not consuming CPU yet (attempt $attempt/3); retrying"; continue
      fi
      echo "[run] competitor restarted on cpu$comp_cpu, confirmed actually executing"; return 0
    done
    echo "[run] ERROR could not restart unreserved competitor, actually running, after 3 attempts"; return 1
  else
    local attempt landed comp_pod
    for attempt in 1 2 3; do
      delete_manifest "$FIXED_COMP_FILE"
      wait_manifest_gone "$FIXED_COMP_FILE"
      wait_cpus_free "$comp_cpu"
      sed "s/@@REQUESTED_CPUS@@/$comp_cpu/g" "$FIXED_COMP_FILE" | kubectl create -f - >/dev/null 2>&1
      if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=competitor" \
            --for=condition=Ready --timeout=150s >/dev/null 2>&1; then
        echo "[run] restarted competitor not Ready (attempt $attempt/3); retrying"; continue
      fi
      comp_pod=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=competitor" -o jsonpath='{.items[0].metadata.name}')
      landed=$(kubectl -n "$NS" exec "$comp_pod" -- printenv RT_CPUSET 2>/dev/null | cut -d, -f1 | cut -d- -f1)
      if [ "$landed" = "$comp_cpu" ]; then
        if ! confirm_burning_cpu "$comp_pod"; then
          echo "[run] competitor restarted on cpu$comp_cpu but not consuming CPU yet (attempt $attempt/3); retrying"; continue
        fi
        echo "[run] competitor restarted, re-landed on cpu$comp_cpu, confirmed actually executing"; return 0
      fi
      echo "[run] restarted competitor landed on cpu$landed, needed cpu$comp_cpu (attempt $attempt/3); retrying"
    done
    echo "[run] ERROR could not restart reserved competitor back onto cpu$comp_cpu, actually running, after 3 attempts"
    return 1
  fi
}

teardown_fixed_competitor() {
  [ "$HAS_COMP" != 1 ] && return 0
  kubectl -n "$NS" delete pod -l "app=$MODEL,role=interferer" --ignore-not-found --wait=true >/dev/null 2>&1
  kubectl -n "$NS" delete pod -l "app=$MODEL,role=competitor" --ignore-not-found --wait=true >/dev/null 2>&1
  [ -n "${FIXED_COMP_FILE:-}" ] && delete_manifest "$FIXED_COMP_FILE"
}

FAILED_CELLS=(); FAILED_FILES=()
SKIPPED_CELLS=()

run_one_cell() {
  f="$1"
  scale=$(basename "$(dirname "$f")"); ul=$(basename "$f" .yaml)   # ul like U0.5
  sub="$scale/$ul"; out="results/${MODEL}${OUT_TAG}/$scale/$ul"
  echo "[run] === $sub ($f) ==="
  mkdir -p "$out"

  key="${scale}-U${ul#U}"
  cv=$(python3 -c "
import json
try:
    d = json.load(open('models/$MODEL/$TAB_NAME'))
except FileNotFoundError:
    print('NA'); raise SystemExit
print(d.get('$key', {}).get('cv', 'NA'))
" 2>/dev/null)
  if [ -z "$cv" ] || [ "$cv" = "NA" ]; then
    echo "[run] ERROR $sub: no calibration entry for $key in $TAB_NAME -- run: python calibrate.py $MODEL -- skipping"
    SKIPPED_CELLS+=("$sub: not calibrated"); return
  fi
  if ! python3 -c "raise SystemExit(0 if float('$cv') <= $CV_THRESHOLD else 1)" 2>/dev/null; then
    echo "[run] ERROR $sub: calibration cv=$cv > $CV_THRESHOLD (mis-calibrated K?) -- run: python calibrate.py $MODEL --force -- skipping"
    SKIPPED_CELLS+=("$sub: high-cv calibration ($cv > $CV_THRESHOLD)"); return
  fi

  EXPECTED_N=$(grep -oE -- '--n-jobs [0-9]+' "$f" | head -1 | grep -oE '[0-9]+')
  EXPECTED_N="${EXPECTED_N:-5000}"

  CELL_OK=0; n_got=0; fail_reason=""
  for cell_attempt in $(seq 1 "$CELL_ATTEMPTS"); do
    [ "$cell_attempt" -gt 1 ] && echo "[run] --- retrying cell (attempt $cell_attempt/$CELL_ATTEMPTS): $fail_reason ---"

    if [ "$HAS_NB" = 1 ]; then
      desired_target_cpu=""
      nb_file="models/$MODEL/$GEN_DIR/_nb/$scale/$ul.yaml"
      : "${NB_HINT_CPU:=$(pick_paired_cpu)}"
      delete_manifest "$nb_file"
      wait_manifest_gone "$nb_file"
      wait_cpus_free "$NB_HINT_CPU"
      sed "s/@@REQUESTED_CPUS@@/$NB_HINT_CPU/g" "$nb_file" | kubectl create -f - >/dev/null
      if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=neighbour" \
            --for=condition=Ready --timeout=150s >/dev/null 2>&1; then
        fail_reason="neighbour pod not Ready"
        echo "[run] $fail_reason; retrying cell"
        delete_manifest "$nb_file"
        continue
      fi
      nb_pod=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=neighbour" -o jsonpath='{.items[0].metadata.name}')
      nb_cpu=$(kubectl -n "$NS" exec "$nb_pod" -- printenv RT_CPUSET 2>/dev/null | cut -d, -f1 | cut -d- -f1)
      if [ "$nb_cpu" = "$KEEP_CPU" ]; then
        fail_reason="neighbour landed on KEEP_CPU=$KEEP_CPU"
        echo "[run] $fail_reason; retrying cell"
        delete_manifest "$nb_file"
        continue
      fi
      desired_target_cpu=$(siblings_of "$nb_cpu" | tr ' ' '\n' | grep -vx "$nb_cpu" | head -1)
      [ -z "$desired_target_cpu" ] && desired_target_cpu="$nb_cpu"
      if [ "$desired_target_cpu" = "$KEEP_CPU" ]; then
        fail_reason="neighbour's sibling is KEEP_CPU=$KEEP_CPU (would force target there)"
        echo "[run] $fail_reason; retrying cell"
        delete_manifest "$nb_file"
        continue
      fi
      if ! confirm_burning_cpu "$nb_pod"; then
        fail_reason="neighbour on cpu$nb_cpu is Ready but not consuming CPU (RT budget grant still incomplete?)"
        echo "[run] $fail_reason; retrying cell"
        delete_manifest "$nb_file"
        continue
      fi
      echo "[run] neighbour placed+running on cpu$nb_cpu, confirmed actually executing; target will be forced onto its sibling cpu$desired_target_cpu"
    fi

    if [ -n "$PIN_RTCPU" ]; then
      CPU_CANDIDATES=("$PIN_RTCPU"); FORCE_CPU=1
    elif [ "$HAS_NB" = 1 ] || [ "$HAS_COMP" = 1 ]; then
      read -ra CPU_CANDIDATES <<< "$desired_target_cpu"; FORCE_CPU=1
    else
      CPU_CANDIDATES=(); FORCE_CPU=0
    fi
    tgt_hint=""
    [ "$FORCE_CPU" = 1 ] && tgt_hint=$(IFS=,; echo "${CPU_CANDIDATES[*]}")

    placed=0; tgt=""; tgt_cpuset=""; rtcpu=""
    for attempt in $(seq 1 "$PIN_ATTEMPTS"); do
      delete_manifest "$f"
      wait_manifest_gone "$f"
      wait_cpus_free "$tgt_hint"
      sed "s/@@REQUESTED_CPUS@@/$tgt_hint/g" "$f" | kubectl create -f - >/dev/null
      if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=target" \
            --for=condition=Ready --timeout=120s >/dev/null 2>&1; then
        echo "[run] target not Ready (attempt $attempt/$PIN_ATTEMPTS)"; continue
      fi
      tgt=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=target" -o jsonpath='{.items[0].metadata.name}')
      tgt_cpuset=$(kubectl -n "$NS" exec "$tgt" -- printenv RT_CPUSET 2>/dev/null || true)
      rtcpu=$(echo "$tgt_cpuset" | cut -d, -f1 | cut -d- -f1)
      if [ "$FORCE_CPU" = 1 ]; then
        match=0
        for c in "${CPU_CANDIDATES[@]}"; do [ "$rtcpu" = "$c" ] && match=1 && break; done
        if [ "$match" != 1 ]; then
          echo "[run] target on cpu$rtcpu, wanted one of {${CPU_CANDIDATES[*]}} ($attempt/$PIN_ATTEMPTS); re-placing"; continue
        fi
      fi
      if [ "$MT_THREADS" -gt 1 ] 2>/dev/null; then
        mt_cpus=$(expand_cpuset "$tgt_cpuset")
        mt_n=$(echo $mt_cpus | wc -w)
        if [ "$mt_n" -ne "$MT_THREADS" ]; then
          echo "[run] target RT_CPUSET=$tgt_cpuset resolved to $mt_n cpu(s), need $MT_THREADS ($attempt/$PIN_ATTEMPTS); re-placing"; continue
        fi
        mt_c1=$(echo $mt_cpus | cut -d' ' -f1); mt_c2=$(echo $mt_cpus | cut -d' ' -f2)
        if echo " $(siblings_of "$mt_c1") " | grep -q " $mt_c2 "; then
          echo "[run] target pair {$mt_c1,$mt_c2} are SMT siblings, need distinct physical cores ($attempt/$PIN_ATTEMPTS); re-placing"; continue
        fi
        if [ "$mt_c1" = "$KEEP_CPU" ] || [ "$mt_c2" = "$KEEP_CPU" ]; then
          echo "[run] target pair {$mt_c1,$mt_c2} includes KEEP_CPU=$KEEP_CPU ($attempt/$PIN_ATTEMPTS); re-placing"; continue
        fi
      fi
      placed=1; break
    done
    if [ "$placed" = 0 ]; then
      if [ "$FORCE_CPU" = 1 ]; then
        fail_reason="could not place target on any of {${CPU_CANDIDATES[*]}} after $PIN_ATTEMPTS attempts"
      else
        fail_reason="could not place target after $PIN_ATTEMPTS attempts"
      fi
      echo "[run] $fail_reason; giving up on this cell"
      delete_manifest "$f"
      [ "$HAS_NB" = 1 ] && delete_manifest "$nb_file"
      break
    fi

    if { [ "$HAS_NB" = 1 ] || [ "$HAS_COMP" = 1 ]; }; then
      match=0
      for c in "${CPU_CANDIDATES[@]}"; do [ "$rtcpu" = "$c" ] && match=1 && break; done
      if [ "$match" != 1 ]; then
        fail_reason="target landed on cpu$rtcpu despite being forced to one of {${CPU_CANDIDATES[*]}} -- placement forcing did not hold"
        echo "[run] BUG: $fail_reason; retrying cell"
        delete_manifest "$f"
        [ "$HAS_NB" = 1 ] && delete_manifest "$nb_file"
        continue
      fi
    fi
    [ "$HAS_NB" = 1 ] && echo "[run] neighbour on cpu$nb_cpu, target forced to sibling cpu$rtcpu -- confirmed same physical core, neighbour already running"
    [ "$HAS_COMP" = 1 ] && echo "[run] competitor fixed on cpu$comp_cpu, target forced to cpu$rtcpu -- confirmed, competitor already running for this whole scale"

    if [ "$HAS_COMP" = 1 ]; then
      comp_role="interferer"; [ "$COMPETITOR_TYPE" = "reserved" ] && comp_role="competitor"
      comp_pod_now=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=$comp_role" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
      if [ -z "$comp_pod_now" ] || ! confirm_burning_cpu "$comp_pod_now"; then
        fail_reason="competitor not consuming CPU for this cell (Ready/Running but quiet -- transient RT-bandwidth perturbation?)"
        echo "[run] $fail_reason; retrying cell"
        delete_manifest "$f"
        continue
      fi
      echo "[run] competitor re-confirmed actually executing for this cell"
    fi

    cat > "$out/placement.json" <<JSON
{"model":"$MODEL","scale":"$scale","U":"${ul#U}","target_pod":"$tgt","target_RT_CPUSET":"$tgt_cpuset","pair_type":"$PAIR_TYPE","competitor_type":"$COMPETITOR_TYPE","competitor_cpu":"${comp_cpu:-}","neighbour_cpu":"${nb_cpu:-}","cell_attempt":$cell_attempt}
JSON

    steer_out=""; irq_before=""
    if [ -n "$IRQ_STEER" ] && [ -n "$rtcpu" ]; then
      steer_out=$(kubectl -n "$NS" exec -i "$AGENT" -- bash -s -- "$IRQ_STEER" "$rtcpu" < node-prep/steer-irqs.sh 2>/dev/null)
      irq_before=$(kubectl -n "$NS" exec "$AGENT" -- awk -v c=$((rtcpu + 2)) 'NR>1{s+=$c} END{print s+0}' /proc/interrupts 2>/dev/null)
      echo "[run] IRQ_STEER=$IRQ_STEER rtcpu=$rtcpu -> ${steer_out:-<none>}"
    fi

    echo "[run] running..."
    comp_died=0
    comp_role=""
    [ "$HAS_COMP" = 1 ] && { comp_role="interferer"; [ "$COMPETITOR_TYPE" = "reserved" ] && comp_role="competitor"; }
    comp_last_cputime=""; comp_stall_count=0
    liveness_log="$out/corunner_liveness.log"; : > "$liveness_log"
    for _ in $(seq 1 5000); do
      ph=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=target" \
           -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
      [ "$ph" = "Succeeded" ] && break
      [ "$ph" = "Failed" ] && { echo "[run] target Failed"; break; }
      if [ -n "$comp_role" ]; then
        comp_pod_now=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=$comp_role" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        comp_ph=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=$comp_role" \
             -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
        stalled=0
        if [ "$comp_ph" != "Running" ] || [ -z "$comp_pod_now" ]; then
          stalled=1
          echo "$(date -u +%FT%TZ) phase=${comp_ph:-gone} cputime=NA stall_count=NA -- not Running" >> "$liveness_log"
        else
          cur=$(pod_cputime "$comp_pod_now")
          if [ -z "$cur" ]; then
            stalled=1
            echo "$(date -u +%FT%TZ) phase=$comp_ph cputime=read_failed" >> "$liveness_log"
          elif [ -n "$comp_last_cputime" ] && [ "$cur" -le "$comp_last_cputime" ] 2>/dev/null; then
            stalled=1
            echo "$(date -u +%FT%TZ) phase=$comp_ph cputime=$cur (no advance since $comp_last_cputime)" >> "$liveness_log"
          else
            echo "$(date -u +%FT%TZ) phase=$comp_ph cputime=$cur" >> "$liveness_log"
          fi
          comp_last_cputime="$cur"
        fi
        if [ "$stalled" = 1 ]; then
          comp_stall_count=$((comp_stall_count + 1))
        else
          comp_stall_count=0
        fi
        if [ "$comp_stall_count" -ge 2 ]; then
          echo "[run] WARNING competitor/interferer stalled ($comp_stall_count consecutive checks, no cpu progress or not Running) mid-run; attempting restart"
          if ! restart_fixed_competitor; then
            comp_died=1; break
          fi
          comp_last_cputime=""; comp_stall_count=0
        fi
      fi
      sleep 2
    done
    if [ "$comp_died" = 1 ]; then
      fail_reason="competitor died mid-cell and could not be restarted"
      echo "[run] $fail_reason; retrying cell"
      delete_manifest "$f"
      continue
    fi

    kubectl exec -n "$NS" "$AGENT" -- cat "/host$HOST_PATH/$sub/target/jobs.csv" > "$out/jobs.csv" 2>/dev/null
    total_lines=$(wc -l < "$out/jobs.csv" 2>/dev/null || echo 0)
    n_got=$(( total_lines >= 2 ? total_lines - 2 : 0 ))   # minus '#'-comment + header

    if [ -n "$comp_role" ]; then
      comp_subdir="intf"; [ "$COMPETITOR_TYPE" = "reserved" ] && comp_subdir="comp"
      comp_n=$(kubectl exec -n "$NS" "$AGENT" -- sh -c "wc -l < /host$HOST_PATH/${COMP_FIXED_SUB:-$sub}/$comp_subdir/jobs.csv" 2>/dev/null)
      echo "[run] co-runner ($comp_role) own jobs.csv row count at cell end: ${comp_n:-unknown}" | tee -a "$liveness_log"
    fi

    if [ -n "$IRQ_STEER" ] && [ -n "$rtcpu" ]; then
      irq_after=$(kubectl -n "$NS" exec "$AGENT" -- awk -v c=$((rtcpu + 2)) 'NR>1{s+=$c} END{print s+0}' /proc/interrupts 2>/dev/null)
      delta=$(( ${irq_after:-0} - ${irq_before:-0} ))
      printf '{"arm":"%s","steer":%s,"irqs_on_rtcpu_during_run":%d}\n' \
        "$IRQ_STEER" "${steer_out:-null}" "$delta" > "$out/irq.json"
      echo "[run] interrupts serviced on RT cpu$rtcpu during run: $delta"
    fi

    if [ "$n_got" -eq "$EXPECTED_N" ]; then
      echo "[run] collected $n_got/$EXPECTED_N rows -> $out"
      delete_manifest "$f"
      [ "$HAS_NB" = 1 ] && delete_manifest "$nb_file"
      CELL_OK=1; break
    fi
    fail_reason="collected $n_got/$EXPECTED_N rows"
    echo "[run] WARNING $sub: $fail_reason (attempt $cell_attempt/$CELL_ATTEMPTS)"
    delete_manifest "$f"
    [ "$HAS_NB" = 1 ] && delete_manifest "$nb_file"
    sleep 5
  done

  if [ "$CELL_OK" != 1 ]; then
    echo "[run] FAILED $sub after $CELL_ATTEMPTS attempt(s): $fail_reason"
    FAILED_CELLS+=("$sub: $fail_reason")
    FAILED_FILES+=("$f")
  fi

  kubectl -n "$NS" delete pod -l "app=$MODEL,role=neighbour" --ignore-not-found --wait=false >/dev/null 2>&1
  delete_manifest "$f"
  [ "$HAS_NB" = 1 ] && delete_manifest "$nb_file"
  sleep 12   # let the driver release the claim before the next cell
}

if [ "$HAS_COMP" = 1 ]; then
  mapfile -t SCALES_LIST < <(for f in "${FILES[@]}"; do basename "$(dirname "$f")"; done | sort -u)
  for scale in "${SCALES_LIST[@]}"; do
    mapfile -t scale_files < <(printf '%s\n' "${FILES[@]}" | grep "/$GEN_DIR/$scale/")
    [ ${#scale_files[@]} -eq 0 ] && continue
    first_ul=$(basename "${scale_files[0]}" .yaml)
    scale_period=$(grep -oE -- '--period-us [0-9]+' "${scale_files[0]}" | head -1 | grep -oE '[0-9]+')
    [ -n "$scale_period" ] && ensure_qos_period "$scale_period"

    if ! place_fixed_competitor "$scale" "$first_ul"; then
      echo "[run] skipping all of $scale (competitor setup failed)"
      for f in "${scale_files[@]}"; do
        sub="$scale/$(basename "$f" .yaml)"
        FAILED_CELLS+=("$sub: competitor setup failed for $scale")
      done
      continue
    fi
    COMP_FIXED_SUB="$scale/$first_ul"

    for f in "${scale_files[@]}"; do run_one_cell "$f"; done

    if [ ${#FAILED_FILES[@]} -gt 0 ]; then
      echo
      echo "[run] --- ${#FAILED_FILES[@]} cell(s) failed in $scale; retrying once more (competitor still running) ---"
      RETRY_FILES=("${FAILED_FILES[@]}")
      FAILED_FILES=()
      mapfile -t FAILED_CELLS < <(printf '%s\n' "${FAILED_CELLS[@]}" | grep -v "^$scale/")
      for f in "${RETRY_FILES[@]}"; do run_one_cell "$f"; done
    fi

    teardown_fixed_competitor
  done
else
  prev_scale=""
  for f in "${FILES[@]}"; do
    scale=$(basename "$(dirname "$f")")
    if [ "$scale" != "$prev_scale" ]; then
      scale_period=$(grep -oE -- '--period-us [0-9]+' "$f" | head -1 | grep -oE '[0-9]+')
      [ -n "$scale_period" ] && ensure_qos_period "$scale_period"
      prev_scale="$scale"
    fi
    run_one_cell "$f"
  done

  if [ ${#FAILED_FILES[@]} -gt 0 ]; then
    echo
    echo "[run] --- ${#FAILED_FILES[@]} cell(s) failed during the main sweep; retrying them once more now that the rest of the sweep is done ---"
    RETRY_FILES=("${FAILED_FILES[@]}")
    FAILED_CELLS=(); FAILED_FILES=()
    for f in "${RETRY_FILES[@]}"; do run_one_cell "$f"; done
  fi
fi

echo
ALL_BAD_CELLS=("${SKIPPED_CELLS[@]}" "${FAILED_CELLS[@]}")
if [ ${#ALL_BAD_CELLS[@]} -eq 0 ]; then
  echo "[run] done. all ${#FILES[@]} cell(s) collected their expected row count."
else
  echo "[run] done. ${#ALL_BAD_CELLS[@]}/${#FILES[@]} cell(s) did not produce valid data -- do not trust these:"
  [ ${#SKIPPED_CELLS[@]} -gt 0 ] && printf '  - %s [not retried -- calibration issue, fix and rerun]\n' "${SKIPPED_CELLS[@]}"
  [ ${#FAILED_CELLS[@]} -gt 0 ] && printf '  - %s [failed even after end-of-sweep retry]\n' "${FAILED_CELLS[@]}"
fi
echo "[run] results under results/${MODEL}${OUT_TAG}/"
