#!/usr/bin/env bash
# M4 - MIGRATION: cost of involuntary vCPU/thread migration & cold cache.
#
#   condition : isolated, quiet host, SAME set/U, two arms differing only in
#               affinity: PINNED to a fixed core set vs FREE (scheduler may
#               migrate). Run under CFS so migration is the only variable.
#   predict   : free arm shows a slightly heavier tail (exec_us / wait_us bumps
#               at migration instants); median ~ unchanged. Modest effect.
#   finding if: free >> pinned in miss ratio -> migration is a first-order
#               factor (notable; usually it is second-order).
#
# Required env:
#   PINNED_CPUS   fixed core set for the pinned arm, e.g. "0,1"
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

: "${PINNED_CPUS:?set PINNED_CPUS, e.g. 0,1 (see scripts/cpu_topology.sh)}"

print_model "M4-migration" \
    "same set/U; CFS pinned (${PINNED_CPUS}) vs free affinity" \
    "free: heavier tail at migration instants; median ~ unchanged" \
    "free >> pinned miss ratio (migration is first-order)"

export MODES="${MODES:-vanilla}"
export INTERFERENCE="none"
export PER_JOB_ATTR="1"
export TASKSETS_DIR="$(filter_tasksets "/tmp/ts-m4" "${U_REGEX:-_U(1\.20|1\.40)\.json}")"

echo "### arm: PINNED (${PINNED_CPUS})" >&2
CPUSET="${PINNED_CPUS}" run_model "m4-migration/pinned"

echo "### arm: FREE (no pinning)" >&2
CPUSET="" run_model "m4-migration/free"
