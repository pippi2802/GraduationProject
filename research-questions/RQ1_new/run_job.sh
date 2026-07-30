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
# model3 only: how the target's OWN m=2 pair is placed --
#   sibling  -> both cpus are the two SMT threads of ONE physical core [default]
#   physical -> one cpu from each of two DIFFERENT physical cores
PAIR_TYPE="${PAIR_TYPE:-sibling}"
# model3 only: what occupies the pair's spare cpu (the one the target's own
# thread does NOT pin to) --
#   unreserved -> CFS matmul, taskset-pinned directly                [default]
#   reserved   -> its own CBS reservation (co_runners.competitor.u)
COMPETITOR_TYPE="${COMPETITOR_TYPE:-unreserved}"
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
mapfile -t FILES < <(find "$GLOB" -name 'U*.yaml' -not -path '*/_intf/*' -not -path '*/_comp/*' | sort)
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

FAILED_CELLS=()

for f in "${FILES[@]}"; do
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
    FAILED_CELLS+=("$sub: not calibrated"); continue
  fi
  if ! python3 -c "raise SystemExit(0 if float('$cv') <= $CV_THRESHOLD else 1)" 2>/dev/null; then
    echo "[run] ERROR $sub: calibration cv=$cv > $CV_THRESHOLD (mis-calibrated K?) -- run: python calibrate.py $MODEL --force -- skipping"
    FAILED_CELLS+=("$sub: high-cv calibration ($cv > $CV_THRESHOLD)"); continue
  fi

  EXPECTED_N=$(grep -oE -- '--n-jobs [0-9]+' "$f" | head -1 | grep -oE '[0-9]+')
  EXPECTED_N="${EXPECTED_N:-5000}"

  CELL_OK=0; n_got=0; fail_reason=""
  for cell_attempt in $(seq 1 "$CELL_ATTEMPTS"); do
    [ "$cell_attempt" -gt 1 ] && echo "[run] --- retrying cell (attempt $cell_attempt/$CELL_ATTEMPTS): $fail_reason ---"

    # --- place the target; if PIN_RTCPU is set, retry until its FIRST cpu matches
    placed=0; tgt=""; tgt_cpuset=""; rtcpu=""; sparecpu=""
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
      if [ -n "$PIN_RTCPU" ] && [ "$rtcpu" != "$PIN_RTCPU" ]; then
        echo "[run] target on cpu$rtcpu != PIN_RTCPU=$PIN_RTCPU; re-placing ($attempt/$PIN_ATTEMPTS)"; continue
      fi
      placed=1; break
    done
    if [ "$placed" = 0 ]; then
      fail_reason="could not place target on cpu${PIN_RTCPU:-any} after $PIN_ATTEMPTS attempts"
      echo "[run] $fail_reason; giving up on this cell"
      kubectl delete -f "$f" --ignore-not-found >/dev/null 2>&1
      break
    fi

    # --- model3: verify the target's OWN m=2 pair matches PAIR_TYPE -----------
    actual_pair=""; pair_ok=1
    if [ "$HAS_COMP" = 1 ]; then
      pair=($(expand_cpuset "$tgt_cpuset"))
      sparecpu="${pair[1]:-}"
      if [ -z "$sparecpu" ]; then
        pair_ok=0; fail_reason="m=2 claim only yielded one cpu ($tgt_cpuset)"
      else
        sibs_rt=" $(siblings_of "$rtcpu") "
        case "$sibs_rt" in *" $sparecpu "*) actual_pair="sibling" ;; *) actual_pair="physical" ;; esac
        if [ "$actual_pair" != "$PAIR_TYPE" ]; then
          pair_ok=0; fail_reason="pair landed $actual_pair (cpus $rtcpu,$sparecpu), wanted $PAIR_TYPE"
        fi
      fi
      if [ "$pair_ok" = 0 ]; then
        echo "[run] $fail_reason; retrying cell"
        kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
        continue
      fi
      echo "[run] target pair = $rtcpu,$sparecpu ($actual_pair, matches PAIR_TYPE=$PAIR_TYPE)"
    fi

    # --- model2: verify the reserved neighbour landed on the target's SIBLING -
    nb_ok=1
    if [ "$HAS_NB" = 1 ]; then
      if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=neighbour" \
            --for=condition=Ready --timeout=60s >/dev/null 2>&1; then
        nb_ok=0; fail_reason="neighbour pod not Ready"
      else
        nb_pod=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=neighbour" -o jsonpath='{.items[0].metadata.name}')
        nb_cpuset=$(kubectl -n "$NS" exec "$nb_pod" -- printenv RT_CPUSET 2>/dev/null || true)
        nb_cpu=$(echo "$nb_cpuset" | cut -d, -f1 | cut -d- -f1)
        desired_nb=$(siblings_of "$rtcpu" | tr ' ' '\n' | grep -vx "$rtcpu" | head -1)
        [ -z "$desired_nb" ] && desired_nb="$rtcpu"   # no SMT sibling on this node
        if [ "$nb_cpu" != "$desired_nb" ]; then
          nb_ok=0; fail_reason="neighbour on cpu$nb_cpu, wanted target's sibling cpu$desired_nb (target=cpu$rtcpu)"
        fi
      fi
      if [ "$nb_ok" = 0 ]; then
        echo "[run] $fail_reason; retrying cell"
        kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
        continue
      fi
      echo "[run] neighbour on cpu$nb_cpu = target's sibling (target=cpu$rtcpu) -- confirmed same physical core"
    fi

    # --- model3: place the competitor on the spare cpu ------------------------
    intf_cpu=""; comp_cpu=""; comp_ok=1
    if [ "$HAS_COMP" = 1 ] && [ "$COMPETITOR_TYPE" = "unreserved" ]; then
      intf="models/$MODEL/generated/_intf/$scale/$ul.yaml"
      if [ -f "$intf" ]; then
        intf_cpu="$sparecpu"
        sed "s/@@INTF_CPU@@/$intf_cpu/g" "$intf" | kubectl create -f - >/dev/null 2>&1
        echo "[run] unreserved competitor taskset to spare cpu$intf_cpu"
      else
        echo "[run] WARN _intf manifest missing for $sub; competitor skipped"
      fi
    elif [ "$HAS_COMP" = 1 ] && [ "$COMPETITOR_TYPE" = "reserved" ]; then
      comp="models/$MODEL/generated/_comp/$scale/$ul.yaml"
      if [ -f "$comp" ]; then
        kubectl create -f "$comp" >/dev/null 2>&1
        if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=competitor" \
              --for=condition=Ready --timeout=60s >/dev/null 2>&1; then
          comp_ok=0; fail_reason="reserved competitor pod not Ready"
        else
          comp_pod=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=competitor" -o jsonpath='{.items[0].metadata.name}')
          comp_cpuset=$(kubectl -n "$NS" exec "$comp_pod" -- printenv RT_CPUSET 2>/dev/null || true)
          comp_cpu=$(echo "$comp_cpuset" | cut -d, -f1 | cut -d- -f1)
          if [ "$comp_cpu" != "$sparecpu" ]; then
            comp_ok=0; fail_reason="reserved competitor on cpu$comp_cpu, wanted spare cpu$sparecpu"
          fi
        fi
        if [ "$comp_ok" = 0 ]; then
          echo "[run] $fail_reason; retrying cell"
          kubectl -n "$NS" delete pod -l "app=$MODEL,role=competitor" --ignore-not-found --wait=true >/dev/null 2>&1
          kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
          continue
        fi
        echo "[run] reserved competitor on spare cpu$comp_cpu -- confirmed"
      else
        echo "[run] WARN _comp manifest missing for $sub; competitor skipped"
      fi
    fi

    # persist placement so co-location is a logged FACT, not an inference
    cat > "$out/placement.json" <<JSON
{"model":"$MODEL","scale":"$scale","U":"${ul#U}","target_pod":"$tgt","target_RT_CPUSET":"$tgt_cpuset","pair_type":"$actual_pair","spare_cpu":"$sparecpu","competitor_type":"$COMPETITOR_TYPE","interferer_cpu":"$intf_cpu","reserved_competitor_cpu":"$comp_cpu","neighbour_cpu":"${nb_cpu:-}","cell_attempt":$cell_attempt}
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
    kubectl -n "$NS" delete pod -l "app=$MODEL,role=interferer" --ignore-not-found --wait=false >/dev/null 2>&1
    kubectl -n "$NS" delete pod -l "app=$MODEL,role=competitor" --ignore-not-found --wait=false >/dev/null 2>&1
    kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
    sleep 5
  done

  if [ "$CELL_OK" != 1 ]; then
    echo "[run] FAILED $sub after $CELL_ATTEMPTS attempt(s): $fail_reason"
    FAILED_CELLS+=("$sub: $fail_reason")
  fi

  kubectl -n "$NS" delete pod -l "app=$MODEL,role=interferer" --ignore-not-found --wait=false >/dev/null 2>&1
  kubectl -n "$NS" delete pod -l "app=$MODEL,role=competitor" --ignore-not-found --wait=false >/dev/null 2>&1
  kubectl -n "$NS" delete pod -l "app=$MODEL,role=neighbour" --ignore-not-found --wait=false >/dev/null 2>&1
  kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
  sleep 12   # let the driver release the claim before the next cell
done

echo
if [ ${#FAILED_CELLS[@]} -eq 0 ]; then
  echo "[run] done. all ${#FILES[@]} cell(s) collected their expected row count."
else
  echo "[run] done. ${#FAILED_CELLS[@]}/${#FILES[@]} cell(s) FAILED -- do not trust these until rerun:"
  printf '  - %s\n' "${FAILED_CELLS[@]}"
fi
echo "[run] analyze with: python result.py ${MODEL}${OUT_TAG}"
