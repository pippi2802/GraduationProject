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
mapfile -t FILES < <(find "$GLOB" -name 'U*.yaml' | sort)
[ ${#FILES[@]} -eq 0 ] && { echo "ERROR: no manifests; run generate_yaml.py $MODEL"; exit 1; }
echo "[run] model=$MODEL ns=$NS agent=$AGENT cells=${#FILES[@]}"

for f in "${FILES[@]}"; do
  scale=$(basename "$(dirname "$f")"); ul=$(basename "$f" .yaml)   # ul like U0.5
  sub="$scale/$ul"; out="results/$MODEL/$scale/$ul"
  echo "[run] === $sub ($f) ==="
  kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
  kubectl create -f "$f" >/dev/null

  # target must become Ready (skip cell if it never places, e.g. over-subscribe)
  if ! kubectl wait -n "$NS" pod -l "app=$MODEL,role=target" \
        --for=condition=Ready --timeout=120s >/dev/null 2>&1; then
    echo "[run] target not Ready; skipping"; kubectl delete -f "$f" --ignore-not-found >/dev/null 2>&1; continue
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
  mkdir -p "$out"
  kubectl exec -n "$NS" "$AGENT" -- cat "/host$HOST_PATH/$sub/target/jobs.csv" > "$out/jobs.csv" 2>/dev/null
  if [ -s "$out/jobs.csv" ]; then echo "[run] collected $(wc -l < "$out/jobs.csv") lines -> $out"; \
     else echo "[run] WARN empty jobs.csv"; fi

  kubectl delete -f "$f" --ignore-not-found --wait=true >/dev/null 2>&1
  sleep 12   # let the driver release the claim before the next cell
done
echo "[run] done. analyze with: python result.py $MODEL"
