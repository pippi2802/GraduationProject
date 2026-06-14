#!/usr/bin/env bash
# Iterate every task set x {rtdra, vanilla}, run on the cluster, collect JSONL.
#
# For each (taskset, mode):
#   1. (optional) start the best-effort interference pod on the node,
#   2. create a ConfigMap holding the taskset JSON,
#   3. substitute the pod template (and the claim, rtdra only) and apply,
#   4. wait for completion, copy /out/metrics.jsonl to results/<mode>/<set>.jsonl,
#   5. delete pods/claim/configmap, cool-down, next.
#
# A per-run one-line summary is printed: mode, n, U, miss_ratio, p99_resp_us.
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration (override via environment)
# ---------------------------------------------------------------------------
NS="${NS:-kdl-bench}"
NODE="${NODE:-rt-cluster-worker-0}"                              # RT worker node
IMAGE="${IMAGE:-docker.io/pippina2/kdl-workload:latest}"         # workload image
IMAGE_INTERF="${IMAGE_INTERF:-docker.io/pippina2/kdl-interference:latest}"
MODES="${MODES:-rtdra vanilla}"
INTERFERENCE="${INTERFERENCE:-on}"              # on|none
CPU_WORKERS="${CPU_WORKERS:-4}"
JOBS="${JOBS:-1000}"
WARMUP="${WARMUP:-20}"
COOLDOWN="${COOLDOWN:-5}"                        # seconds between runs
TIMEOUT="${TIMEOUT:-600}"                        # per-pod completion timeout (s)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deploy"
TASKSETS_DIR="${TASKSETS_DIR:-${ROOT_DIR}/gen/tasksets}"
RESULTS_DIR="${RESULTS_DIR:-${ROOT_DIR}/results}"

mkdir -p "${RESULTS_DIR}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
json_get() { # json_get <file> <key>
    python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$1" "$2"
}
json_res() { # json_res <file> <q_us|p_us|m>
    python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['reservation'][sys.argv[2]])" "$1" "$2"
}

render() { # render <template> <out>  -- substitutes {{VAR}} from exported env
    local tmpl="$1" out="$2"
    sed \
        -e "s|{{IMAGE}}|${IMAGE}|g" \
        -e "s|{{IMAGE_INTERF}}|${IMAGE_INTERF}|g" \
        -e "s|{{TASKSET}}|${TASKSET}|g" \
        -e "s|{{TASKSET_ID}}|${TASKSET_ID}|g" \
        -e "s|{{Q}}|${Q}|g" \
        -e "s|{{P}}|${P}|g" \
        -e "s|{{M}}|${M}|g" \
        -e "s|{{RUN_ID}}|${RUN_ID}|g" \
        -e "s|{{NODE}}|${NODE}|g" \
        -e "s|{{JOBS}}|${JOBS}|g" \
        -e "s|{{WARMUP}}|${WARMUP}|g" \
        -e "s|{{UTIL}}|${UTIL}|g" \
        -e "s|{{N_TASKS}}|${N_TASKS}|g" \
        -e "s|{{INTERFERENCE}}|${INTERFERENCE}|g" \
        -e "s|{{CPU_WORKERS}}|${CPU_WORKERS}|g" \
        "${tmpl}" > "${out}"
}

summarize() { # summarize <jsonl>  -> "miss_ratio p99_resp_us"
    python3 - "$1" <<'PY'
import json, sys
jobs = []
try:
    with open(sys.argv[1]) as f:
        for line in f:
            line = line.strip()
            if line:
                jobs.append(json.loads(line))
except FileNotFoundError:
    print("nan nan"); raise SystemExit
if not jobs:
    print("nan nan"); raise SystemExit
miss = sum(1 for j in jobs if j.get("deadline_miss")) / len(jobs)
resp = sorted(j["response_time_us"] for j in jobs)
p99 = resp[min(len(resp) - 1, int(0.99 * len(resp)))]
print(f"{miss:.4f} {p99}")
PY
}

cleanup_run() {
    kubectl -n "${NS}" delete pod "rt-workload-${RUN_ID}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
    kubectl -n "${NS}" delete pod "vanilla-workload-${RUN_ID}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
    kubectl -n "${NS}" delete pod "interference-${RUN_ID}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
    kubectl -n "${NS}" delete resourceclaim "rt-claim-${RUN_ID}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
    kubectl -n "${NS}" delete configmap "taskset-${RUN_ID}" --ignore-not-found --wait=false >/dev/null 2>&1 || true
}

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
kubectl apply -f "${DEPLOY_DIR}/namespace.yaml" >/dev/null

echo "mode,n,U,miss_ratio,p99_resp_us"

shopt -s nullglob
for ts_file in "${TASKSETS_DIR}"/*.json; do
    TASKSET="$(basename "${ts_file}")"
    TASKSET_ID="$(json_get "${ts_file}" taskset_id)"
    N_TASKS="$(json_get "${ts_file}" n)"
    UTIL="$(json_get "${ts_file}" util)"
    Q="$(json_res "${ts_file}" q_us)"
    P="$(json_res "${ts_file}" p_us)"
    M="$(json_res "${ts_file}" m)"

    for MODE in ${MODES}; do
        RUN_ID="${MODE}-${TASKSET_ID}-U${UTIL}"
        # Sanitize into a valid RFC1123 name: lowercase, only [a-z0-9-],
        # and no leading/trailing '-' (printf avoids a trailing newline that
        # tr would otherwise turn into a trailing dash).
        RUN_ID="$(printf '%s' "${RUN_ID}" | tr -c 'a-zA-Z0-9-' '-' | tr 'A-Z' 'a-z' | sed -e 's/^-*//' -e 's/-*$//')"
        mkdir -p "${RESULTS_DIR}/${MODE}"
        out_jsonl="${RESULTS_DIR}/${MODE}/${TASKSET_ID}.jsonl"

        cleanup_run

        # taskset ConfigMap (mounted at /tasksets)
        kubectl -n "${NS}" create configmap "taskset-${RUN_ID}" \
            --from-file="${TASKSET}=${ts_file}" >/dev/null

        # optional interference
        if [ "${INTERFERENCE}" = "on" ]; then
            tmp_if="$(mktemp)"
            render "${DEPLOY_DIR}/pod-interference.yaml.tmpl" "${tmp_if}"
            kubectl apply -f "${tmp_if}" >/dev/null
            rm -f "${tmp_if}"
        fi

        if [ "${MODE}" = "rtdra" ]; then
            tmp_claim="$(mktemp)"
            render "${DEPLOY_DIR}/resourceclaim-rt.yaml" "${tmp_claim}"
            kubectl apply -f "${tmp_claim}" >/dev/null
            rm -f "${tmp_claim}"
            pod_name="rt-workload-${RUN_ID}"
            tmpl="${DEPLOY_DIR}/pod-rtdra.yaml.tmpl"
        else
            pod_name="vanilla-workload-${RUN_ID}"
            tmpl="${DEPLOY_DIR}/pod-vanilla.yaml.tmpl"
        fi

        tmp_pod="$(mktemp)"
        render "${tmpl}" "${tmp_pod}"
        kubectl apply -f "${tmp_pod}" >/dev/null
        rm -f "${tmp_pod}"

        # wait for completion
        kubectl -n "${NS}" wait --for=condition=Ready "pod/${pod_name}" \
            --timeout=120s >/dev/null 2>&1 || true
        if ! kubectl -n "${NS}" wait --for=jsonpath='{.status.phase}'=Succeeded \
                "pod/${pod_name}" --timeout="${TIMEOUT}s" >/dev/null 2>&1; then
            echo "WARN: ${pod_name} did not Succeed within ${TIMEOUT}s" >&2
        fi

        # copy metrics out of the (now terminated) pod's emptyDir via cp
        kubectl -n "${NS}" cp "${pod_name}:/out/metrics.jsonl" "${out_jsonl}" \
            -c workload >/dev/null 2>&1 || echo "WARN: cp failed for ${pod_name}" >&2

        read -r miss p99 <<<"$(summarize "${out_jsonl}")"
        echo "${MODE},${N_TASKS},${UTIL},${miss},${p99}"

        cleanup_run
        sleep "${COOLDOWN}"
    done
done

echo "all runs complete. results in ${RESULTS_DIR}" >&2
