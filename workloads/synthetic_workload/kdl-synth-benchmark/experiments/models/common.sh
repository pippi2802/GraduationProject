#!/usr/bin/env bash
# Shared helpers for the RQ1 virtualization "models" (experiments/models/*.sh).
#
# Each model script is a thin wrapper over experiments/run_all.sh that (a) prints
# the model's condition / prediction / falsifier (so the run is a test of a
# written-down expectation, not open-ended measurement) and (b) exports the
# harness knobs that realise the condition. Results land under
# results/<model>/<mode>/<taskset>.jsonl and are analysed with
# analysis/attribute.py.
set -euo pipefail

MODELS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENTS_DIR="$(cd "${MODELS_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${EXPERIMENTS_DIR}/.." && pwd)"
RUN_ALL="${EXPERIMENTS_DIR}/run_all.sh"
ALL_TASKSETS="${ROOT_DIR}/gen/tasksets"

# print_model <name> <condition> <prediction> <falsifier>
print_model() {
    cat >&2 <<EOF
=============================================================================
MODEL: $1
  condition : $2
  predict   : $3
  finding if: $4
=============================================================================
EOF
}

# filter_tasksets <dst_dir> <U_regex>
# Symlink the tasksets whose filename U matches <U_regex> into <dst_dir> and
# echo <dst_dir>. Filenames are setNNN_nX_UY.YY.json. Empty regex = all.
filter_tasksets() {
    local dst="$1" ure="${2:-}"
    rm -rf "${dst}"; mkdir -p "${dst}"
    local f base
    for f in "${ALL_TASKSETS}"/*.json; do
        base="$(basename "${f}")"
        if [ -z "${ure}" ] || printf '%s' "${base}" | grep -Eq "${ure}"; then
            ln -sf "${f}" "${dst}/${base}"
        fi
    done
    echo "${dst}"
}

# run_model <results_subdir> -- invokes run_all.sh with the already-exported env.
run_model() {
    local sub="$1"
    export RESULTS_DIR="${ROOT_DIR}/results/${sub}"
    mkdir -p "${RESULTS_DIR}"
    echo "# results -> ${RESULTS_DIR}" >&2
    bash "${RUN_ALL}"
}
