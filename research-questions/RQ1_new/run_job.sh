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

read -r NS HOST_PATH HAS_NB HAS_COMP < <(python3 - "$MODEL" <<'PY'
import sys, yaml
c = yaml.safe_load(open(f"models/{sys.argv[1]}/config.yaml"))
cr = c.get("co_runners") or {}
print(c["namespace"], c["host_path"],
      int(bool(cr.get("neighbours"))),
      int("interferer" in cr or "competitor" in cr))
PY
)
AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no node agent; run node-prep/apply.sh $MODEL"; exit 1; }

GLOB="models/$MODEL/generated/${SCALE:+$SCALE/}"
[ -n "$SCALE" ] && GLOB="models/$MODEL/generated/$SCALE" || GLOB="models/$MODEL/generated"
mapfile -t FILES < <(find "$GLOB" -name 'U*.yaml' -not -path '*/_intf/*' -not -path '*/_comp/*' -not -path '*/_nb/*' | sort)
[ ${#FILES[@]} -eq 0 ] && { echo "ERROR: no manifests; run generate_yaml.py $MODEL"; exit 1; }
echo "[run] model=$MODEL ns=$NS agent=$AGENT cells=${#FILES[@]} has_neighbours=$HAS_NB has_competitor=$HAS_COMP"
[ "$HAS_COMP" = 1 ] && echo "[run] model3 arm: PAIR_TYPE=$PAIR_TYPE COMPETITOR_TYPE=$COMPETITOR_TYPE"

# "0-3"/"0,2" -> "0 1 2 3" / "0 2"
expand_cpuset() {
  echo "$1" | tr ',' '\n' | while read -r p; do
    case "$p" in *-*) seq "${p%-*}" "${p#*-}" ;; "") ;; *) echo "$p" ;; esac
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

# --- model3: place the (fixed-intensity) competitor/interferer ONCE for a
# whole scale, and compute the target's forced cpu relative to it. Sets the
# globals desired_target_cpu, comp_cpu, FIXED_COMP_FILE (empty for the
# unreserved arm, which has no separate claim objects to clean up). Neither
# comp_cpu nor desired_target_cpu is ever allowed to be KEEP_CPU (see its
# definition above). Returns 1 if the competitor never came up or no such
# cpu pair could be found/landed.
place_fixed_competitor() {
  local scale="$1" first_ul="$2"
  desired_target_cpu=""; comp_cpu=""; FIXED_COMP_FILE=""
  [ "$HAS_COMP" != 1 ] && return 0

  if [ "$COMPETITOR_TYPE" = "unreserved" ]; then
    local intf="models/$MODEL/generated/_intf/$scale/$first_ul.yaml"
    [ -f "$intf" ] || { echo "[run] ERROR _intf manifest missing for $scale"; return 1; }
    # WE choose the competitor's cpu directly (taskset, no driver involved) --
    # pick the first candidate, excluding KEEP_CPU, that leaves at least one
    # valid PAIR_TYPE-relative target cpu once KEEP_CPU is filtered out.
    local c candidate_target
    for c in $(all_cpus | sort -n); do
      [ "$c" = "$KEEP_CPU" ] && continue
      candidate_target=$(filter_keep_cpu "$(target_cpu_for "$c")")
      if [ -n "$candidate_target" ]; then
        comp_cpu="$c"; desired_target_cpu="$candidate_target"; break
      fi
    done
    if [ -z "$comp_cpu" ]; then
      echo "[run] ERROR no (competitor,target) cpu pair avoiding KEEP_CPU=$KEEP_CPU for PAIR_TYPE=$PAIR_TYPE"
      return 1
    fi
    sed "s/@@INTF_CPU@@/$comp_cpu/g" "$intf" | kubectl create -f - >/dev/null 2>&1
    if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=interferer" \
          --for=condition=Ready --timeout=150s >/dev/null 2>&1; then
      echo "[run] ERROR unreserved competitor pod not Ready for $scale"
      kubectl -n "$NS" delete pod -l "app=$MODEL,role=interferer" --ignore-not-found >/dev/null 2>&1
      return 1
    fi
    echo "[run] $scale: unreserved competitor fixed on cpu$comp_cpu (avoiding KEEP_CPU=$KEEP_CPU), running for the whole scale"
  elif [ "$COMPETITOR_TYPE" = "reserved" ]; then
    FIXED_COMP_FILE="models/$MODEL/generated/_comp/$scale/$first_ul.yaml"
    [ -f "$FIXED_COMP_FILE" ] || { echo "[run] ERROR _comp manifest missing for $scale"; return 1; }
    # the driver decides this cpu (worst-fit, uncontrolled) -- re-place if it
    # lands on KEEP_CPU, or if its PAIR_TYPE-relative target cpu would be
    # KEEP_CPU (e.g. it landed on KEEP_CPU's own sibling for PAIR_TYPE=sibling).
    local ok=0 attempt comp_pod landed candidate_target
    for attempt in 1 2 3 4 5; do
      kubectl delete -f "$FIXED_COMP_FILE" --ignore-not-found --wait=true >/dev/null 2>&1
      kubectl create -f "$FIXED_COMP_FILE" >/dev/null 2>&1
      if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=competitor" \
            --for=condition=Ready --timeout=150s >/dev/null 2>&1; then
        echo "[run] reserved competitor pod not Ready ($scale, attempt $attempt/5); retrying"; continue
      fi
      comp_pod=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=competitor" -o jsonpath='{.items[0].metadata.name}')
      landed=$(kubectl -n "$NS" exec "$comp_pod" -- printenv RT_CPUSET 2>/dev/null | cut -d, -f1 | cut -d- -f1)
      if [ "$landed" = "$KEEP_CPU" ]; then
        echo "[run] reserved competitor landed on KEEP_CPU=$KEEP_CPU ($scale, attempt $attempt/5); re-placing"; continue
      fi
      candidate_target=$(filter_keep_cpu "$(target_cpu_for "$landed")")
      if [ -z "$candidate_target" ]; then
        echo "[run] reserved competitor on cpu$landed has no usable pair avoiding KEEP_CPU=$KEEP_CPU ($scale, attempt $attempt/5); re-placing"; continue
      fi
      comp_cpu="$landed"; desired_target_cpu="$candidate_target"; ok=1; break
    done
    if [ "$ok" != 1 ]; then
      echo "[run] ERROR reserved competitor never landed on a usable cpu (avoiding KEEP_CPU=$KEEP_CPU) for $scale after 5 attempts"
      kubectl delete -f "$FIXED_COMP_FILE" --ignore-not-found >/dev/null 2>&1
      return 1
    fi
    echo "[run] $scale: reserved competitor landed on cpu$comp_cpu (avoiding KEEP_CPU=$KEEP_CPU), running for the whole scale"
  fi

  echo "[run] $scale: target will be forced onto {$desired_target_cpu} for every cell (PAIR_TYPE=$PAIR_TYPE vs competitor cpu$comp_cpu)"
}

teardown_fixed_competitor() {
  [ "$HAS_COMP" != 1 ] && return 0
  kubectl -n "$NS" delete pod -l "app=$MODEL,role=interferer" --ignore-not-found --wait=false >/dev/null 2>&1
  kubectl -n "$NS" delete pod -l "app=$MODEL,role=competitor" --ignore-not-found --wait=false >/dev/null 2>&1
  [ -n "${FIXED_COMP_FILE:-}" ] && kubectl delete -f "$FIXED_COMP_FILE" --ignore-not-found --wait=false >/dev/null 2>&1
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
    SKIPPED_CELLS+=("$sub: not calibrated"); continue
  fi
  if ! python3 -c "raise SystemExit(0 if float('$cv') <= $CV_THRESHOLD else 1)" 2>/dev/null; then
    echo "[run] ERROR $sub: calibration cv=$cv > $CV_THRESHOLD (mis-calibrated K?) -- run: python calibrate.py $MODEL --force -- skipping"
    SKIPPED_CELLS+=("$sub: high-cv calibration ($cv > $CV_THRESHOLD)"); continue
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
      nb_file="models/$MODEL/generated/_nb/$scale/$ul.yaml"
      kubectl delete -f "$nb_file" --ignore-not-found --wait=true >/dev/null 2>&1
      kubectl create -f "$nb_file" >/dev/null
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
      sleep 5   # let the neighbour clear its own warm-up before the target starts
      echo "[run] neighbour placed+running on cpu$nb_cpu; target will be forced onto its sibling cpu$desired_target_cpu"
    fi

    # --- place the target ----------------------------------------------------
    # The driver only accepts `count` (how many cores), never WHICH ones -- so
    # there is no request we can make that targets a specific cpu directly.
    # PIN_RTCPU (explicit, user-requested), model2's neighbour-sibling forcing
    # (exactly one valid cpu), and model3's competitor-relative forcing
    # (desired_target_cpu, computed once per scale by place_fixed_competitor
    # -- possibly SEVERAL valid cpus for PAIR_TYPE=physical) all reduce to the
    # same thing: a SET of acceptable cpus (one element for PIN_RTCPU/model2),
    # checked per attempt, delete + recreate until the SMT-blind worst-fit
    # driver happens to land on ANY member of that set -- not cycling through
    # trying to force one specific member per attempt, which would reject
    # equally-valid landings just because they weren't the one currently
    # being tried.
    if [ -n "$PIN_RTCPU" ]; then
      CPU_CANDIDATES=("$PIN_RTCPU"); FORCE_CPU=1
    elif [ "$HAS_NB" = 1 ] || [ "$HAS_COMP" = 1 ]; then
      read -ra CPU_CANDIDATES <<< "$desired_target_cpu"; FORCE_CPU=1
    else
      CPU_CANDIDATES=(); FORCE_CPU=0
    fi

    placed=0; tgt=""; tgt_cpuset=""; rtcpu=""
    for attempt in $(seq 1 "$PIN_ATTEMPTS"); do
      kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
      kubectl create -f "$f" >/dev/null
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

    # wait for the target pod to Complete (Succeeded)
    echo "[run] running..."
    for _ in $(seq 1 1000); do
      ph=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=target" \
           -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
      [ "$ph" = "Succeeded" ] && break
      [ "$ph" = "Failed" ] && { echo "[run] target Failed"; break; }
      sleep 10
    done

    # pull jobs.csv off the node via the agent
    kubectl exec -n "$NS" "$AGENT" -- cat "/host$HOST_PATH/$sub/target/jobs.csv" > "$out/jobs.csv" 2>/dev/null
    total_lines=$(wc -l < "$out/jobs.csv" 2>/dev/null || echo 0)
    n_got=$(( total_lines >= 2 ? total_lines - 2 : 0 ))   # minus '#'-comment + header

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
    mapfile -t scale_files < <(printf '%s\n' "${FILES[@]}" | grep "/generated/$scale/")
    [ ${#scale_files[@]} -eq 0 ] && continue
    first_ul=$(basename "${scale_files[0]}" .yaml)

    if ! place_fixed_competitor "$scale" "$first_ul"; then
      echo "[run] skipping all of $scale (competitor setup failed)"
      for f in "${scale_files[@]}"; do
        sub="$scale/$(basename "$f" .yaml)"
        FAILED_CELLS+=("$sub: competitor setup failed for $scale")
      done
      continue
    fi

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
  for f in "${FILES[@]}"; do run_one_cell "$f"; done

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
