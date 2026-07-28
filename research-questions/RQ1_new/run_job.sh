#!/usr/bin/env bash
# run_job.sh <model> [soft|tight] — run the generated sweep, one cell at a time.
#
# Mirrors kuberay's run_job.sh: loop the generated manifests, create each, wait for
# the target to finish, pull its jobs.csv off the node, delete, next. Requires the
# node agent (node-prep/apply.sh <model>) for frequency pinning + reading results.
set -uo pipefail
MODEL="${1:?usage: run_job.sh <model> [soft|tight]}"
SCALE="${2:-}"
cd "$(dirname "$0")"

read -r NS HOST_PATH < <(python3 - "$MODEL" <<'PY'
import sys, yaml
c = yaml.safe_load(open(f"models/{sys.argv[1]}/config.yaml"))
print(c["namespace"], c["host_path"])
PY
)
AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no node agent; run node-prep/apply.sh $MODEL"; exit 1; }

GLOB="models/$MODEL/generated/${SCALE:+$SCALE/}"
[ -n "$SCALE" ] && GLOB="models/$MODEL/generated/$SCALE" || GLOB="models/$MODEL/generated"
mapfile -t FILES < <(find "$GLOB" -name 'U*.yaml' -not -path '*/_intf/*' | sort)
[ ${#FILES[@]} -eq 0 ] && { echo "ERROR: no manifests; run generate_yaml.py $MODEL"; exit 1; }
echo "[run] model=$MODEL ns=$NS agent=$AGENT cells=${#FILES[@]}"

for f in "${FILES[@]}"; do
  scale=$(basename "$(dirname "$f")"); ul=$(basename "$f" .yaml)   # ul like U0.5
  sub="$scale/$ul"; out="results/$MODEL/$scale/$ul"
  echo "[run] === $sub ($f) ==="
  mkdir -p "$out"
  kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
  kubectl create -f "$f" >/dev/null

  # target must become Ready (skip cell if it never places, e.g. over-subscribe)
  if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=target" \
        --for=condition=Ready --timeout=120s >/dev/null 2>&1; then
    echo "[run] target not Ready; skipping"; kubectl delete -f "$f" --ignore-not-found >/dev/null 2>&1; continue
  fi

  # record where the driver actually placed the target (proof of co-location)
  tgt=$(kubectl -n "$NS" get pod -l "app=$MODEL,role=target" -o jsonpath='{.items[0].metadata.name}')
  tgt_cpuset=$(kubectl -n "$NS" exec "$tgt" -- printenv RT_CPUSET 2>/dev/null || true)

  # model3: pin an UNRESERVED interferer on the target's REAL SMT sibling
  # (relative placement: read where the driver put the target, resolve its sibling).
  intf="models/$MODEL/generated/_intf/$scale/$ul.yaml"
  intf_cpu=""; sibs=""; is_sibling="n/a"
  if [ -f "$intf" ]; then
    rtcpu=$(echo "$tgt_cpuset" | cut -d, -f1 | cut -d- -f1)
    if [ -n "$rtcpu" ]; then
      sibs=$(kubectl -n "$NS" exec "$AGENT" -- cat "/sys/devices/system/cpu/cpu$rtcpu/topology/thread_siblings_list" 2>/dev/null)
      sib=$(echo "$sibs" | tr ',-' '  ' | tr ' ' '\n' | grep -vx "$rtcpu" | head -1)
      # is the resolved interferer CPU a genuine sibling (different logical cpu, same core)?
      if [ -n "$sib" ] && [ "$sib" != "$rtcpu" ]; then is_sibling="true"; else is_sibling="false"; fi
      [ -z "$sib" ] && sib="$rtcpu"
      intf_cpu="$sib"
      echo "[run] interferer on sibling cpu=$sib (target cpu=$rtcpu, siblings=$sibs, is_sibling=$is_sibling)"
      sed "s/@@INTF_CPU@@/$sib/g" "$intf" | kubectl create -f - >/dev/null 2>&1
    else
      echo "[run] WARN could not read RT_CPUSET; interferer skipped"
    fi
  fi

  # persist placement so sibling-vs-separate-core is a logged FACT, not an inference
  cat > "$out/placement.json" <<JSON
{"model":"$MODEL","scale":"$scale","U":"${ul#U}","target_pod":"$tgt","target_RT_CPUSET":"$tgt_cpuset","interferer_cpu":"$intf_cpu","thread_siblings_list":"$sibs","interferer_on_sibling":"$is_sibling"}
JSON

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
  if [ -s "$out/jobs.csv" ]; then echo "[run] collected $(wc -l < "$out/jobs.csv") lines -> $out"; \
     else echo "[run] WARN empty jobs.csv"; fi

  kubectl -n "$NS" delete pod -l "app=$MODEL,role=interferer" --ignore-not-found --wait=false >/dev/null 2>&1
  kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
  sleep 12   # let the driver release the claim before the next cell
done
echo "[run] done. analyze with: python result.py $MODEL"
