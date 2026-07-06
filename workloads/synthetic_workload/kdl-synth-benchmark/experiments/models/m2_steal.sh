#!/usr/bin/env bash
# M2 - STEAL: does vCPU steal alone break an admitted set? (mechanism A)
#
#   condition : rtdra, admitted set, but the pCPU is CONTENDED - a best-effort
#               noisy neighbour saturates the host (CPU_WORKERS high). On public
#               cloud, approximate a busy host either this way or with co-tenant
#               stress VMs pinned to the same PPG (see docs).
#   predict   : miss ratio rises; response-time bimodal (2nd mode ~ +1 steal
#               burst ~ one period, ms-scale); misses correlate with steal_us
#               and preempt_us; tardiness_us ~ steal burst.
#   finding if: miss ratio barely moves under heavy host pressure -> steal is
#               NOT the dominant break (contradicts the field's assumption).
#
# Env you may override:
#   CPU_WORKERS  best-effort stressor threads (default: oversubscribe)
#   U_REGEX      taskset U filter
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

print_model "M2-steal" \
    "rtdra, admitted set, oversubscribed host (best-effort neighbour)" \
    "miss up; response bimodal; miss correlates with steal_us/preempt_us" \
    "miss ratio flat under heavy host pressure (steal not the cause)"

export MODES="rtdra"
export INTERFERENCE="on"
export CPU_WORKERS="${CPU_WORKERS:-8}"          # > vCPUs on D4s_v5 (4) => oversubscribe
export PER_JOB_ATTR="1"
export TASKSETS_DIR="$(filter_tasksets "/tmp/ts-m2" "${U_REGEX:-_U(0\.80|1\.00|1\.20)\.json}")"

run_model "m2-steal"
