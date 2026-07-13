#!/usr/bin/env bash
# SHARED covariate-sampler deployer for the RQ1 deterministic-probe models
# (model1_1, model2, model3, model4). Renders the common DaemonSet template for
# the requested model and loads the SHARED sampler (common/sampler/sampler.py)
# into a ConfigMap. Only the sampler is shared here — node-prep and analysis stay
# per-model.
#
# Usage:
#   ../common/sampler/apply.sh <model> [hostdir] [node-model]
#
#   <model>       k8s namespace + resource-name prefix (must be DNS-safe),
#                 e.g. model2, model3, model4, model1-1
#   [hostdir]     /var/lib/<hostdir> path on the node
#                 (default: <model> with '-' -> '_', so model1-1 -> model1_1)
#   [node-model]  nodeSelector experiment-model value   (default: <model>)
#
# Examples:
#   ../common/sampler/apply.sh model2                    # ns model2,  /var/lib/model2,   node model2
#   ../common/sampler/apply.sh model3                    # ns model3,  /var/lib/model3,   node model3
#   ../common/sampler/apply.sh model4                    # ns model4,  /var/lib/model4,   node model4
#   ../common/sampler/apply.sh model1-1 model1_1 model1  # ns model1-1,/var/lib/model1_1, node model1
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MODEL="${1:?usage: apply.sh <model> [hostdir] [node-model]  (e.g. apply.sh model2)}"
HOSTDIR="${2:-${MODEL//-/_}}"
NODE_MODEL="${3:-$MODEL}"

SAMPLER="$HERE/sampler.py"
TEMPLATE="$HERE/sampler-daemonset.yaml.template"
[[ -f "$SAMPLER" ]]  || { echo "ERROR: shared sampler not found at $SAMPLER"   >&2; exit 1; }
[[ -f "$TEMPLATE" ]] || { echo "ERROR: template not found at $TEMPLATE"        >&2; exit 1; }

RENDERED="$(mktemp)"; trap 'rm -f "$RENDERED"' EXIT
sed -e "s|@@MODEL@@|$MODEL|g" \
    -e "s|@@HOSTDIR@@|$HOSTDIR|g" \
    -e "s|@@NODE_MODEL@@|$NODE_MODEL|g" \
    "$TEMPLATE" > "$RENDERED"

kubectl create namespace "$MODEL" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$MODEL" create configmap "${MODEL}-sampler-scripts" \
  --from-file="sampler.py=$SAMPLER" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$RENDERED"
kubectl -n "$MODEL" rollout status "ds/${MODEL}-sampler" --timeout=180s || true
echo "[apply] sampler applied for $MODEL (shared common/sampler)." \
     "Streams -> /var/lib/$HOSTDIR/samples." \
     "Verify: kubectl -n $MODEL get pods -l app=${MODEL}-sampler -o wide"
