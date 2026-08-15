#!/usr/bin/env bash
# run_job.sh <model> [soft|tight] — run the generated sweep, one cell at a time.
#
# Mirrors kuberay's run_job.sh: loop the generated manifests, create each, wait for
# the target to finish, pull its jobs.csv off the node, delete, next. Requires the
# node agent (node-prep/apply.sh <model>) for frequency pinning + reading results.
#
# Every cell is now validated before it's accepted (see CELL_ATTEMPTS below): a
# bad calibration, a placement that didn't land where the model requires, or a
# short jobs.csv all trigger an automatic retry instead of silently recording bad
# data. Cells that still fail after retrying are listed in the final summary —
# check that list before trusting a sweep's results.
set -uo pipefail
MODEL="${1:?usage: run_job.sh <model> [soft|tight]}"
SCALE="${2:-}"
cd "$(dirname "$0")"

# --- model2/model3 placement knobs ------------------------------------------
# model3 only: how the target is placed relative to the (fixed-intensity)
# competitor. The competitor's own utilization never changes across the U
# sweep (co_runners.competitor.u), so it's created ONCE per scale (see
# place_fixed_competitor below) and left running for every cell of that
# scale -- the target (count:1, same as model1/model2's own claim) is then
# forced onto a cpu computed once, relative to the competitor's actual
# landed cpu --
#   sibling  -> target's cpu is the competitor's SMT sibling (same physical
#               core)                                              [default]
#   physical -> target's cpu is on a DIFFERENT physical core than the
#               competitor
PAIR_TYPE="${PAIR_TYPE:-sibling}"
# model3 only: what the competitor actually is --
#   unreserved -> CFS matmul, taskset-pinned to a cpu WE choose directly (it
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
# IRQ steering arm (model4 only): unset | off | on.
IRQ_STEER="${IRQ_STEER:-}"
# pin the target's FIRST cpu to a specific logical cpu for stable, comparable
# placement. The SMT-blind driver has no core knob, so we delete+recreate until
# worst-fit lands there (up to PIN_ATTEMPTS). Empty = accept whatever it picks.
PIN_RTCPU="${PIN_RTCPU:-}"
PIN_ATTEMPTS="${PIN_ATTEMPTS:-8}"
# how many times to redo a whole cell (placement + competitor/neighbour landing
# + run + row-count) before giving up and recording it as FAILED.
CELL_ATTEMPTS="${CELL_ATTEMPTS:-4}"
# calibration gate: refuse to run a cell whose recorded calibration cv is above
# this (mis-calibrated K / genuinely broken measurement). One flat value for
# both scales -- investigated 2026-07-30 (steal time, SMT-sibling load, and
# frequency/governor pinning all directly ruled out as causes; see
# memory/rq1_calibration_noise_floor.md): short-duration cells (tight-scale,
# plus soft-scale's own shortest cell soft-U0.1) have an intrinsic noise floor
# up to ~0.04, so 0.05 clears that while still catching genuinely bad cells.
CV_THRESHOLD="${CV_THRESHOLD:-0.05}"
WORKLOAD_KIND="${WORKLOAD:-matmul}"
TAB_NAME="k_table.json"; [ "$WORKLOAD_KIND" != "matmul" ] && TAB_NAME="k_table.$WORKLOAD_KIND.json"
# must match generate_yaml.py's out_root exactly -- separate tree per
# workload so a matmul run and a ptrchase run for the same model never
# silently overwrite each other's manifests.
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
# cells above a utilization cap (e.g. model3 sibling arms' ~0.95 shared-core
# ceiling, where anything beyond it is genuinely infeasible and would just
# burn CELL_ATTEMPTS*PIN_ATTEMPTS retries for nothing). U_MIN=U_MAX=<value>
# isolates exactly one cell -- useful for manually re-running a single cell
# that failed a prior sweep (e.g. bad luck on driver placement) without
# re-running everything else.
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
[ "$HAS_COMP" = 1 ] && echo "[run] model3 arm: PAIR_TYPE=$PAIR_TYPE COMPETITOR_TYPE=$COMPETITOR_TYPE"
[ "$MT_THREADS" -gt 1 ] 2>/dev/null && echo "[run] model4: target_threads=$MT_THREADS, forcing the claimed pair onto two DISTINCT PHYSICAL cores"

# "0-3"/"0,2" -> "0 1 2 3" / "0 2"
# CORRECTED 2026-08-12: hyphen here is the driver's plain delimiter (see the
# same fix in every model4*/job.yaml's own RT_CPUSET normalization), never a
# range -- treat it exactly like a comma. The other caller (siblings_of)
# already strips hyphens to spaces before calling this, so that caller's
# behavior is unaffected either way; this only changes the mt_cpus check
# below, which was the one actually reading a driver-supplied cpuset.
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
# that case, not just the first one found. Treating "physical" as if it had
# one correct answer would make the placement retry loop reject perfectly
# valid landings just because they weren't the arbitrary first candidate
# checked. Empty output means no valid target cpu exists at all (e.g.
# PAIR_TYPE=sibling on a cpu with no SMT sibling). Does NOT know about
# KEEP_CPU -- callers filter that out themselves (filter_keep_cpu below).
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
# list -- e.g. filter_keep_cpu "0 2 3" -> "2 3". Works uniformly whether the
# input is a single cpu (sibling case) or a list (physical case).
filter_keep_cpu() {
  echo "$1" | tr ' ' '\n' | grep -vx "$KEEP_CPU" | grep -v '^$' | tr '\n' ' ' | sed 's/ *$//'
}

# 2026-08-14: `kubectl delete -f <manifest> --wait=true` was found (under
# 4-models-parallel load) to sometimes return before EVERY object it deletes
# is actually gone -- direct evidence: "AlreadyExists: object is being
# deleted" on the very next create, for the RtClaimParameters and
# ResourceClaimTemplate as well as the Pod, not just the Pod. This matters
# beyond just avoiding the error: the driver only releases a cpu from its
# own NodeAllocationState bookkeeping once the underlying (auto-generated)
# ResourceClaim is actually gone, so recreating too early risks the driver
# treating the retry as a genuinely new admission against still-committed
# capacity -- plausible explanation for target landings observed on the
# wrong cpu (worst-fit fallback) instead of the requested one. Polls with
# `kubectl get -f` against the SAME manifest delete just used, which checks
# every object it declares (params + claim template + pod) in one call, not
# just the pod. Returns 1 if still present after ~15s -- caller's own outer
# retry loop already handles that, unchanged from before this existed.
wait_manifest_gone() {
  local file="$1" i
  for i in $(seq 1 15); do
    [ -z "$(kubectl get -f "$file" -o name 2>/dev/null)" ] && return 0
    sleep 1
  done
  return 1
}

# 2026-08-15: wait_manifest_gone only confirms the pod/claim OBJECTS are
# gone from the Kubernetes API -- traced through the driver's actual Go
# source (cmd/dra-rt-kubeletplugin/state.go's Unprepare(), driver.go's
# NodeUnprepareResources) and found that is NOT the same moment the cpu is
# actually released. Kubelet calls the driver's NodeUnprepareResources (the
# thing that decrements NodeAllocationState.spec.allocatedUtilToCpu, the
# real headroom accounting allocate() checks) as a LATER, separate node-
# level step, after the pod object can already be gone from etcd. A retry
# can therefore see "object gone" and request the same cpu again while the
# driver still considers it committed -- explains landings on the wrong cpu
# under heavy concurrent load instead of the one just hinted. This polls
# the driver's own bookkeeping directly: NodeAllocationState is named after
# the node itself, namespace dra-rt-driver (confirmed via `kubectl get
# nodeallocationstates -A`). NODE_NAME is resolved once and cached (matches
# this model's fixed nodeSelector, same "experiment-model=<model>" label
# every config.yaml already uses).
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
# Same check for every cpu in a space- or comma-separated hint list (the
# target's requestedCpus can be multiple candidates for PAIR_TYPE=physical).
wait_cpus_free() {
  local c
  for c in $(echo "$1" | tr ',' ' '); do
    wait_cpu_free "$c"
  done
}

# Deterministically pick a fixed cpu (avoiding KEEP_CPU) that also has a
# valid PAIR_TYPE-relative pair partner (also avoiding KEEP_CPU). Topology
# never changes cell to cell, so this always returns the same answer -- used
# as a requestedCpus HINT (2026-08-14) so the driver lands the
# neighbour/competitor there on the first attempt instead of worst-fit +
# delete/recreate-until-landed. Same selection the unreserved-competitor
# branch already did ad hoc; factored out so model2's neighbour and the
# reserved competitor can reuse it too. Empty output means no valid cpu
# exists at all on this node for the current PAIR_TYPE (caller's existing
# error handling covers that, same as before this hint existed).
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

# `kubectl wait --for=condition=Ready` (used for the neighbour/competitor
# everywhere below) only proves the container process STARTED -- not that it
# actually holds real RT bandwidth yet. Getting that is a separate step (the
# per-pod leaf cgroup rt_runtime is grown on demand under the shared
# kubepods.slice cap); if that grant is still in flight or lands short
# (e.g. the previous cell's pods haven't finished releasing their share back
# to the pool yet), the co-runner can be Ready, correctly pinned to the right
# cpu, and still sit there barely executing -- a cell that then looks
# deceptively clean (low/no contention) for a reason that has nothing to do
# with the reservation actually protecting anything. Confirms real execution
# is happening by sampling the pod's pid-1 utime+stime twice, a few seconds
# apart, and checking it actually advanced. Returns 1 (caller should retry
# the cell/placement) if it didn't move or couldn't be read.
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
# unlike confirm_burning_cpu this is cheap enough to call every poll iteration
# of the mid-run watch loop; the caller compares consecutive samples itself to
# detect a stall. Echoes the value, or nothing on failure (caller must check).
pod_cputime() {
  kubectl -n "$NS" exec "$1" -- awk '{print $14+$15}' /proc/1/stat 2>/dev/null
}

# A QoS slice's cpu.rt_period_us is ONE shared, file-wide value for the WHOLE
# QoS class on that node -- not per-cell, not per-model. Once ANY pod is
# admitted at a given period, that period sticks; a later pod requesting a
# DIFFERENT period (e.g. a tight-scale cell, period 10000, after an earlier
# soft-scale cell left it at 100000) collides with it: the kernel rejects the
# new period while any existing per-cpu runtime entry there would now exceed
# it, and every subsequent admission on that node fails with EINVAL until
# it's reset -- found 2026-08-07, cost real time re-diagnosing the same thing
# across three different nodes by hand. This resets it automatically, once
# per scale, before anything for that scale is created.
#
# Which slice: every model's target today has no requests/limits set at all,
# so every model is BestEffort in practice (confirmed: every pod describe
# this whole session shows QoS Class: BestEffort) -- kubepods-besteffort.slice
# is the right default, but it's NOT hardcoded assuming that stays true.
# Override with QOS_SLICE if a model ever runs Burstable instead (fs2/cpu.go's
# own ancestor chain is: BestEffort -> kubepods-besteffort.slice, Burstable ->
# kubepods-burstable.slice, Guaranteed -> no intermediate slice at all, sits
# directly under kubepods.slice -- which already has its own protected floor
# from today's runc fix, so Guaranteed pods aren't exposed to this specific
# problem the same way and don't need this function at all).
QOS_SLICE="${QOS_SLICE:-kubepods-besteffort.slice}"
QOS_CG="/sys/fs/cgroup/kubepods.slice/$QOS_SLICE"
#
# Only ever touches the QoS slice -- never root/kubepods (those stay at their
# manual node-level seed from rt-budget-seed.sh). Safe write order: zero
# runtime FIRST (always legal at any current period, kernel rejects a period
# drop while a nonzero runtime would exceed it), THEN write the new period.
#
# Since every model owns its node exclusively (one nodeSelector per model,
# confirmed no cross-model node sharing), it's safe to check only THIS
# namespace's own pods before resetting -- if anything here is still alive,
# skip and warn instead of forcing it, since that means a previous scale's
# teardown hasn't actually finished yet, not that it's safe to proceed.
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
# comp_cpu nor desired_target_cpu is ever allowed to be KEEP_CPU (see its
# definition above). Returns 1 if the competitor never came up or no such
# cpu pair could be found/landed.
place_fixed_competitor() {
  local scale="$1" first_ul="$2"
  desired_target_cpu=""; comp_cpu=""; FIXED_COMP_FILE=""; FIXED_INTF_FILE=""
  [ "$HAS_COMP" != 1 ] && return 0

  if [ "$COMPETITOR_TYPE" = "unreserved" ]; then
    local intf="models/$MODEL/$GEN_DIR/_intf/$scale/$first_ul.yaml"
    FIXED_INTF_FILE="$intf"
    [ -f "$intf" ] || { echo "[run] ERROR _intf manifest missing for $scale"; return 1; }
    # WE choose the competitor's cpu directly (taskset, no driver involved) --
    # pick_paired_cpu already finds the first candidate, excluding KEEP_CPU,
    # that leaves at least one valid PAIR_TYPE-relative target cpu.
    comp_cpu=$(pick_paired_cpu) || comp_cpu=""
    [ -n "$comp_cpu" ] && desired_target_cpu=$(filter_keep_cpu "$(target_cpu_for "$comp_cpu")")
    if [ -z "$comp_cpu" ]; then
      echo "[run] ERROR no (competitor,target) cpu pair avoiding KEEP_CPU=$KEEP_CPU for PAIR_TYPE=$PAIR_TYPE"
      return 1
    fi
    # clean slate first -- a stale interferer from a previous, interrupted run
    # (same scale/first_ul -> same pod name) would otherwise make this create
    # fail silently (AlreadyExists, swallowed by the redirect), leaving
    # comp_cpu/desired_target_cpu computed as if a fresh pod was actually made.
    #
    # Retry-until-actually-executing, same as the reserved branch below --
    # Ready alone was NOT sufficient here either (found 2026-08-05: every
    # round of the unreserved sibling arm showed the same silent-no-contention
    # coin-flip as the reserved arms, just via a different mechanism -- a
    # taskset-pinned CFS process can be Ready and scheduled on the right cpu
    # while still not reliably getting real cpu time under whatever else is
    # contending for that node's CFS runqueue at that moment).
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
    # defensive: a stale competitor pod from a DIFFERENT scale/name (e.g. left
    # over from a previous, interrupted invocation of this script) wouldn't be
    # caught by the file-based delete below (that only targets THIS scale's
    # specific object name) -- but the label-based lookups further down would
    # still match it, possibly picking up its stale cpu instead of the fresh
    # pod's. Clear anything under this role first, regardless of name.
    kubectl -n "$NS" delete pod -l "app=$MODEL,role=competitor" --ignore-not-found --wait=true >/dev/null 2>&1
    # requestedCpus HINT (2026-08-14): pick the cpu deterministically upfront
    # (same selection as the unreserved branch) and ask the driver for it
    # directly, instead of accepting worst-fit's uncontrolled choice and
    # retrying until it happens to land somewhere usable. The retry loop
    # stays as a safety net (Ready/burning-cpu/landed-cpu are all still
    # verified every attempt) -- it should just converge on attempt 1 now.
    local hint_cpu; hint_cpu=$(pick_paired_cpu) || hint_cpu=""
    if [ -z "$hint_cpu" ]; then
      echo "[run] ERROR no (competitor,target) cpu pair avoiding KEEP_CPU=$KEEP_CPU for PAIR_TYPE=$PAIR_TYPE"
      return 1
    fi
    local ok=0 attempt comp_pod landed candidate_target
    for attempt in 1 2 3 4 5; do
      kubectl delete -f "$FIXED_COMP_FILE" --ignore-not-found --wait=true >/dev/null 2>&1
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
      # Ready + correct cpu isn't enough on its own -- see confirm_burning_cpu's
      # comment. Confirm it's actually executing before trusting it for the
      # whole scale; a false "ok" here would silently invalidate every cell
      # of this scale, not just one.
      if ! confirm_burning_cpu "$comp_pod"; then
        echo "[run] reserved competitor on cpu$landed is Ready but not consuming CPU (RT budget grant still incomplete?) ($scale, attempt $attempt/5); re-placing"; continue
      fi
      comp_cpu="$landed"; desired_target_cpu="$candidate_target"; ok=1; break
    done
    if [ "$ok" != 1 ]; then
      echo "[run] ERROR reserved competitor never landed on a usable, actually-running cpu (avoiding KEEP_CPU=$KEEP_CPU) for $scale after 5 attempts"
      kubectl delete -f "$FIXED_COMP_FILE" --ignore-not-found >/dev/null 2>&1
      return 1
    fi
    echo "[run] $scale: reserved competitor landed on cpu$comp_cpu (avoiding KEEP_CPU=$KEEP_CPU), confirmed actually executing, running for the whole scale"
  fi

  echo "[run] $scale: target will be forced onto {$desired_target_cpu} for every cell (PAIR_TYPE=$PAIR_TYPE vs competitor cpu$comp_cpu)"
}

# The competitor/interferer has been observed to exit on its own after a
# sustained run (~34 minutes seen in practice), well before a scale's full
# sweep is done -- root cause not pinned down (matmul.c itself has no
# internal timer/limit that would explain this; likely something external to
# the probe process itself: cgroup/kubelet/scheduler-level, not diagnosed
# further yet). Rather than silently losing contention for the rest of the
# scale, run_one_cell's wait-loop polls for this and calls this to bring it
# back. For the unreserved arm this is exact (we command its cpu directly
# via taskset); for the reserved arm the driver could in principle re-land it
# somewhere else, so this retries until it's back on the SAME comp_cpu the
# scale was already set up with (the target is already running, forced onto
# a cpu chosen relative to THAT specific comp_cpu) -- a different landing
# would silently change the experimental condition mid-run. Returns 1 if it
# can't get back to the same cpu; the caller treats that as a cell failure.
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
      kubectl delete -f "$FIXED_COMP_FILE" --ignore-not-found --wait=true >/dev/null 2>&1
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
  # blocking (--wait=true), deliberately: the next thing that happens is
  # either the NEXT scale's place_fixed_competitor (same role=competitor/
  # role=interferer label selector) or the sweep ending. Since the reserved
  # arm's own pre-delete in place_fixed_competitor targets that NEXT scale's
  # own (differently-named) manifest file, it does NOT wait for THIS scale's
  # object to actually finish terminating -- a non-blocking delete here would
  # leave a window where both the old (terminating) and new pod match the
  # same label selector, and a get/wait could pick either one.
  kubectl -n "$NS" delete pod -l "app=$MODEL,role=interferer" --ignore-not-found --wait=true >/dev/null 2>&1
  kubectl -n "$NS" delete pod -l "app=$MODEL,role=competitor" --ignore-not-found --wait=true >/dev/null 2>&1
  [ -n "${FIXED_COMP_FILE:-}" ] && kubectl delete -f "$FIXED_COMP_FILE" --ignore-not-found --wait=true >/dev/null 2>&1
}

FAILED_CELLS=(); FAILED_FILES=()
# calibration-gate rejections are never retried (retrying won't fix a missing
# or high-cv calibration entry -- the table doesn't change mid-sweep), so they
# never enter FAILED_FILES. Kept in their own array, separate from
# FAILED_CELLS, because FAILED_CELLS gets reset before the end-of-sweep retry
# pass below and would otherwise silently drop these from the final report.
SKIPPED_CELLS=()

# One cell's whole placement+run+collect cycle, as a function so a failed cell
# can be replayed in the end-of-sweep retry pass below without duplicating this
# logic. Shares the caller's variables (no `local`, matching the rest of this
# script) -- each call resets them the same way each loop iteration used to.
run_one_cell() {
  f="$1"
  scale=$(basename "$(dirname "$f")"); ul=$(basename "$f" .yaml)   # ul like U0.5
  sub="$scale/$ul"; out="results/${MODEL}${OUT_TAG}/$scale/$ul"
  echo "[run] === $sub ($f) ==="
  mkdir -p "$out"

  # --- calibration gate: refuse to collect data on a mis-calibrated cell ----
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
    # NOTE: `return`, not `continue` -- run_one_cell is a FUNCTION; its own
    # retry loop hasn't started yet at this point, so `continue` here has no
    # enclosing loop (bash prints "continue: only meaningful in a for/while/
    # until loop" and falls through to the rest of the function instead of
    # skipping it -- found 2026-08-05, every mis-calibrated cell was being
    # collected anyway despite the "skipping" message). `return` exits the
    # function and the OUTER `for f in scale_files` loop naturally moves on.
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

    # --- model2: place the NEIGHBOUR FIRST, confirmed Ready (+ a warm-up
    # buffer) BEFORE the target is even created -- this is what actually
    # guarantees contention is present from the target's very first job,
    # instead of bundling both together and hoping the target doesn't race
    # ahead of the neighbour's own startup. Confirmed in practice: without
    # this, some cells had no real contention because the neighbour wasn't up
    # yet, and others wasted whole-cell retries on "neighbour pod not Ready."
    if [ "$HAS_NB" = 1 ]; then
      desired_target_cpu=""
      nb_file="models/$MODEL/$GEN_DIR/_nb/$scale/$ul.yaml"
      # requestedCpus HINT (2026-08-14): computed once, cached, same idea as
      # model3's fixed competitor -- lands the neighbour deterministically
      # instead of worst-fit + delete/recreate-until-landed, every cell.
      : "${NB_HINT_CPU:=$(pick_paired_cpu)}"
      kubectl delete -f "$nb_file" --ignore-not-found --wait=true >/dev/null 2>&1
      wait_manifest_gone "$nb_file"
      wait_cpus_free "$NB_HINT_CPU"
      sed "s/@@REQUESTED_CPUS@@/$NB_HINT_CPU/g" "$nb_file" | kubectl create -f - >/dev/null
      if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=neighbour" \
            --for=condition=Ready --timeout=150s >/dev/null 2>&1; then
        fail_reason="neighbour pod not Ready"
        echo "[run] $fail_reason; retrying cell"
        kubectl delete -f "$nb_file" --ignore-not-found --wait=true >/dev/null 2>&1
        continue
      fi
      nb_pod=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=neighbour" -o jsonpath='{.items[0].metadata.name}')
      nb_cpu=$(kubectl -n "$NS" exec "$nb_pod" -- printenv RT_CPUSET 2>/dev/null | cut -d, -f1 | cut -d- -f1)
      # never let the neighbour (or, below, the target it forces) land on
      # KEEP_CPU -- see its definition near the top: isolate.sh deliberately
      # leaves that one cpu non-isolated for OS/kubelet housekeeping, so
      # anything sharing its physical core picks up uncontrolled noise on top
      # of the intended experimental contention.
      if [ "$nb_cpu" = "$KEEP_CPU" ]; then
        fail_reason="neighbour landed on KEEP_CPU=$KEEP_CPU"
        echo "[run] $fail_reason; retrying cell"
        kubectl delete -f "$nb_file" --ignore-not-found --wait=true >/dev/null 2>&1
        continue
      fi
      desired_target_cpu=$(siblings_of "$nb_cpu" | tr ' ' '\n' | grep -vx "$nb_cpu" | head -1)
      [ -z "$desired_target_cpu" ] && desired_target_cpu="$nb_cpu"   # no SMT sibling on this node
      if [ "$desired_target_cpu" = "$KEEP_CPU" ]; then
        fail_reason="neighbour's sibling is KEEP_CPU=$KEEP_CPU (would force target there)"
        echo "[run] $fail_reason; retrying cell"
        kubectl delete -f "$nb_file" --ignore-not-found --wait=true >/dev/null 2>&1
        continue
      fi
      # Ready only proves the container process started, not that it already
      # holds real RT bandwidth (see confirm_burning_cpu's comment) -- model2
      # recreates the neighbour fresh on EVERY cell, so this cold-start race
      # gets a chance every single cell, not just once per scale like
      # model3's fixed competitor. Confirm it's actually executing before
      # trusting this cell's contention is real.
      if ! confirm_burning_cpu "$nb_pod"; then
        fail_reason="neighbour on cpu$nb_cpu is Ready but not consuming CPU (RT budget grant still incomplete?)"
        echo "[run] $fail_reason; retrying cell"
        kubectl delete -f "$nb_file" --ignore-not-found --wait=true >/dev/null 2>&1
        continue
      fi
      echo "[run] neighbour placed+running on cpu$nb_cpu, confirmed actually executing; target will be forced onto its sibling cpu$desired_target_cpu"
    fi

    # --- place the target ----------------------------------------------------
    # PIN_RTCPU (explicit, user-requested), model2's neighbour-sibling forcing
    # (exactly one valid cpu), and model3's competitor-relative forcing
    # (desired_target_cpu, computed once per scale by place_fixed_competitor
    # -- possibly SEVERAL valid cpus for PAIR_TYPE=physical) all reduce to the
    # same thing: a SET of acceptable cpus (one element for PIN_RTCPU/model2).
    # requestedCpus HINT (2026-08-14): CPU_CANDIDATES, comma-joined, is passed
    # straight to the driver via job.yaml's @@REQUESTED_CPUS@@ placeholder --
    # len==1 pins exactly that cpu, len>1 (PAIR_TYPE=physical) lets the driver
    # score just those candidates and pick the best one (RequestedCpus'
    # documented "any of these N" mode). The delete+recreate retry loop stays
    # as a safety net (still verifies the actual landed cpu every attempt) --
    # it should just converge on attempt 1 now instead of needing worst-fit to
    # stumble onto a member of the set by chance.
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
      kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
      # 2026-08-14: found under 4-models-in-parallel load that --wait=true
      # returning is not sufficient -- confirmed directly via "AlreadyExists:
      # object is being deleted" on the very next create (params, claim
      # template, AND pod, not just the pod). wait_manifest_gone polls the
      # actual state instead of guessing a fixed delay.
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
      # model4: the driver is SMT-blind and only sees "count=2", never WHICH
      # two cpus -- reject a landing whose pair are SMT siblings of the same
      # physical core (or includes KEEP_CPU) and retry, same delete/recreate
      # technique as everything else here, just checking a pairwise topology
      # relationship instead of membership in a candidate set.
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
      kubectl delete -f "$f" --ignore-not-found >/dev/null 2>&1
      [ "$HAS_NB" = 1 ] && kubectl delete -f "$nb_file" --ignore-not-found >/dev/null 2>&1
      break
    fi

    # --- defensive sanity check, not a retry trigger -- correctness is now
    # guaranteed BY CONSTRUCTION (the target was forced onto a member of the
    # co-runner-relative set above), this just catches the unexpected case
    # loudly instead of silently trusting it.
    if { [ "$HAS_NB" = 1 ] || [ "$HAS_COMP" = 1 ]; }; then
      match=0
      for c in "${CPU_CANDIDATES[@]}"; do [ "$rtcpu" = "$c" ] && match=1 && break; done
      if [ "$match" != 1 ]; then
        fail_reason="target landed on cpu$rtcpu despite being forced to one of {${CPU_CANDIDATES[*]}} -- placement forcing did not hold"
        echo "[run] BUG: $fail_reason; retrying cell"
        kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
        [ "$HAS_NB" = 1 ] && kubectl delete -f "$nb_file" --ignore-not-found --wait=true >/dev/null 2>&1
        continue
      fi
    fi
    [ "$HAS_NB" = 1 ] && echo "[run] neighbour on cpu$nb_cpu, target forced to sibling cpu$rtcpu -- confirmed same physical core, neighbour already running"
    [ "$HAS_COMP" = 1 ] && echo "[run] competitor fixed on cpu$comp_cpu, target forced to cpu$rtcpu -- confirmed, competitor already running for this whole scale"

    # model3 only: the fixed competitor is one persistent process for the
    # WHOLE scale (not recreated per cell), so place_fixed_competitor's own
    # confirm_burning_cpu check (once, at scale start) does NOT prove it's
    # still actually executing for THIS cell specifically. Observed in
    # practice: a persistent, never-restarted competitor can still go quiet
    # on individual cells while staying Ready/Running throughout -- most
    # likely the target's own per-cell delete+recreate (a fresh DEADLINE
    # reservation allocated/deallocated every cell) transiently perturbing
    # the shared kernel RT-bandwidth accounting the competitor's leaf cgroup
    # budget lives under. Re-check right before trusting this specific cell;
    # retry (which recreates the target again) if it's gone quiet.
    if [ "$HAS_COMP" = 1 ]; then
      comp_role="interferer"; [ "$COMPETITOR_TYPE" = "reserved" ] && comp_role="competitor"
      comp_pod_now=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=$comp_role" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
      if [ -z "$comp_pod_now" ] || ! confirm_burning_cpu "$comp_pod_now"; then
        fail_reason="competitor not consuming CPU for this cell (Ready/Running but quiet -- transient RT-bandwidth perturbation?)"
        echo "[run] $fail_reason; retrying cell"
        kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
        continue
      fi
      echo "[run] competitor re-confirmed actually executing for this cell"
    fi

    # persist placement so co-location is a logged FACT, not an inference.
    # model3's competitor_cpu/pair_type are fixed for the whole scale (set
    # once by place_fixed_competitor), not re-discovered per cell.
    cat > "$out/placement.json" <<JSON
{"model":"$MODEL","scale":"$scale","U":"${ul#U}","target_pod":"$tgt","target_RT_CPUSET":"$tgt_cpuset","pair_type":"$PAIR_TYPE","competitor_type":"$COMPETITOR_TYPE","competitor_cpu":"${comp_cpu:-}","neighbour_cpu":"${nb_cpu:-}","cell_attempt":$cell_attempt}
JSON

    # model4: apply the IRQ-steering arm and snapshot the RT core's interrupt count.
    steer_out=""; irq_before=""
    if [ -n "$IRQ_STEER" ] && [ -n "$rtcpu" ]; then
      steer_out=$(kubectl -n "$NS" exec -i "$AGENT" -- bash -s -- "$IRQ_STEER" "$rtcpu" < node-prep/steer-irqs.sh 2>/dev/null)
      irq_before=$(kubectl -n "$NS" exec "$AGENT" -- awk -v c=$((rtcpu + 2)) 'NR>1{s+=$c} END{print s+0}' /proc/interrupts 2>/dev/null)
      echo "[run] IRQ_STEER=$IRQ_STEER rtcpu=$rtcpu -> ${steer_out:-<none>}"
    fi

    # wait for the target pod to Complete (Succeeded). For model3, also watch
    # the fixed competitor/interferer -- it's been observed to exit on its own
    # after a sustained run (see restart_fixed_competitor's comment), and
    # since it's meant to persist for the WHOLE scale (many cells), a cell
    # running late in a long scale could otherwise silently lose contention
    # partway through its own run.
    echo "[run] running..."
    comp_died=0
    comp_role=""
    [ "$HAS_COMP" = 1 ] && { comp_role="interferer"; [ "$COMPETITOR_TYPE" = "reserved" ] && comp_role="competitor"; }
    # continuous liveness audit: found 2026-08-05 that a pre-cell (or even
    # once-per-scale) burning-cpu check is NOT sufficient -- a competitor can
    # pass that check and then go quiet for most of a long cell's duration
    # without ANYTHING noticing, since phase stays "Running" throughout (this
    # is exactly what explained round5 disagreeing with round4 despite both
    # using the same fixed harness). Poll every ~2s instead of 10s, and check
    # actual cputime progress (not just pod phase) every single poll -- 2
    # consecutive stalled samples (~4-6s of zero cpu progress) triggers the
    # same restart path as a genuinely dead pod. Every sample (stalled or not)
    # is appended to $out/corunner_liveness.log so a cell's contention can be
    # AUDITED after the fact, not just trusted from a final pass/fail.
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
      kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
      continue
    fi

    # pull jobs.csv off the node via the agent
    kubectl exec -n "$NS" "$AGENT" -- cat "/host$HOST_PATH/$sub/target/jobs.csv" > "$out/jobs.csv" 2>/dev/null
    total_lines=$(wc -l < "$out/jobs.csv" 2>/dev/null || echo 0)
    n_got=$(( total_lines >= 2 ? total_lines - 2 : 0 ))   # minus '#'-comment + header

    # corroborating end-of-cell check: pull the co-runner's OWN job log (it
    # writes one continuously the whole time it runs, same as the target) and
    # record its row count -- a co-runner that was genuinely active the whole
    # cell should show roughly (elapsed_seconds / its own period) rows. Not a
    # pass/fail gate on its own (the continuous cputime check above is the
    # stronger signal) -- just another line in the same audit trail so a
    # cell's contention claim can be cross-checked two independent ways.
    if [ -n "$comp_role" ]; then
      comp_subdir="intf"; [ "$COMPETITOR_TYPE" = "reserved" ] && comp_subdir="comp"
      # the fixed competitor/interferer is created ONCE per scale, from the
      # scale's first cell's manifest -- its hostPath is baked to THAT cell's
      # sub (see COMPETITOR_RESERVED/INTERFERER templates), not the current
      # one, so every cell after the first must look there too, not at $sub
      # (found 2026-08-06: every cell past the first logged "unknown" here
      # since it was checking a sub the persistent pod never wrote to).
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
      CELL_OK=1; break
    fi
    fail_reason="collected $n_got/$EXPECTED_N rows"
    echo "[run] WARNING $sub: $fail_reason (attempt $cell_attempt/$CELL_ATTEMPTS)"
    kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
    [ "$HAS_NB" = 1 ] && kubectl delete -f "$nb_file" --ignore-not-found --wait=true >/dev/null 2>&1
    sleep 5
  done

  if [ "$CELL_OK" != 1 ]; then
    echo "[run] FAILED $sub after $CELL_ATTEMPTS attempt(s): $fail_reason"
    FAILED_CELLS+=("$sub: $fail_reason")
    FAILED_FILES+=("$f")
  fi

  # NOTE: role=interferer/competitor are NOT torn down here -- for model3 they
  # are fixed for the whole scale (place_fixed_competitor/teardown_fixed_competitor,
  # in the per-scale driving loop below), not recreated per cell.
  kubectl -n "$NS" delete pod -l "app=$MODEL,role=neighbour" --ignore-not-found --wait=false >/dev/null 2>&1
  kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
  [ "$HAS_NB" = 1 ] && kubectl delete -f "$nb_file" --ignore-not-found --wait=true >/dev/null 2>&1
  sleep 12   # let the driver release the claim before the next cell
}

if [ "$HAS_COMP" = 1 ]; then
  # model3: drive per-scale, not per-file -- the competitor is created once
  # per scale (place_fixed_competitor) and must stay up for every cell of
  # that scale, then torn down only once the scale's cells (main pass +
  # retry) are done.
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
    # the fixed competitor/interferer's own jobs.csv lives under THIS sub for
    # the whole scale, regardless of which cell run_one_cell is currently on.
    COMP_FIXED_SUB="$scale/$first_ul"

    for f in "${scale_files[@]}"; do run_one_cell "$f"; done

    # end-of-scale retry: same rationale as model1/2's end-of-sweep retry
    # below, just scoped to this scale so it can reuse the still-running
    # competitor instead of needing to recreate it.
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
  # same besteffort-period reset as the HAS_COMP path above, just scoped per
  # scale instead of per (scale, first_ul) since there's no fixed competitor
  # here to hang the check off of -- track the scale of the previous file and
  # reset whenever it changes (and once at the very start).
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

  # End-of-sweep retry: a cell that failed all CELL_ATTEMPTS during the main
  # pass often failed for a transient reason (cluster momentarily busy) rather
  # than something structural -- give every failed cell one more full attempt
  # after the rest of the sweep has already run, instead of just recording it
  # as permanently lost. Only cells still failing after THIS pass end up in
  # the final FAILED list.
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
echo "[run] analyze with: python result.py ${MODEL}${OUT_TAG}"
