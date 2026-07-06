#!/usr/bin/env bash
# =============================================================================
# Render a Model 1 RT cell (or the canary) to stdout as complete Kubernetes YAML:
#   RtClaimParameters + ResourceClaimTemplate + Pod + rt-app ConfigMap.
#
# DRY: all parameters come from config.yaml via cell_env.py / generate_rtapp.py.
#
# Usage:
#   render.sh <scale> <U> <timeblock>      # e.g. render.sh tight 0.95 tb-20260706-1200
#   render.sh --canary <timeblock>
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

CANARY=0
if [[ "${1:-}" == "--canary" ]]; then
  CANARY=1
  TIMEBLOCK="${2:-tb-example}"
  eval "$(python3 cell_env.py --canary "$TIMEBLOCK")"
  SCALE_ARG=(--scale "$SCALE" --u "$U_LABEL")
  TEMPLATE=canary.template.yaml
else
  SCALE="$1"; U="$2"; TIMEBLOCK="${3:-tb-example}"
  eval "$(python3 cell_env.py "$SCALE" "$U" "$TIMEBLOCK")"
  SCALE_ARG=(--scale "$SCALE" --u "$U")
  TEMPLATE=rt-cell.template.yaml
fi

# 1) rt-app JSON for this cell. No `cpus` is set: the rt-DRA driver pins the
#    container to its allocated core and the entrypoint runs rt-app under
#    `taskset -c $RT_CPUSET`, so the thread inherits the driver-pinned CPU.
TMP_JSON="$(mktemp)"
python3 ../rtapp/generate_rtapp.py "${SCALE_ARG[@]}" \
        --logdir /results --out "$TMP_JSON" 2>/dev/null

# 2) Pod + DRA claim (envsubst over the template). Restrict substitution to OUR
#    placeholders so runtime shell vars in the entrypoint (e.g. $RT_CPUSET) are
#    left intact.
export NAMESPACE RES_RUNTIME RES_PERIOD RES_COUNT RES_CLASS SCALE CELL_ID \
       BASE_IMAGE RTAPP_PKG PULL_POLICY HOST_RESULTS_PATH
SUBST='${NAMESPACE} ${RES_RUNTIME} ${RES_PERIOD} ${RES_COUNT} ${RES_CLASS} ${SCALE} ${CELL_ID} ${BASE_IMAGE} ${RTAPP_PKG} ${PULL_POLICY} ${HOST_RESULTS_PATH}'
envsubst "$SUBST" < "$TEMPLATE"

# 3) rt-app ConfigMap for this cell
echo "---"
kubectl create configmap "$CM_NAME" -n "$NAMESPACE" \
  --from-file=rtapp.json="$TMP_JSON" \
  --dry-run=client -o yaml

rm -f "$TMP_JSON"
