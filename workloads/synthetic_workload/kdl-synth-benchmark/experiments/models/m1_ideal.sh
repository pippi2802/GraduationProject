#!/usr/bin/env bash
# M1 - IDEAL: does an admitted set survive virtualization alone?
#
#   condition : rtdra, CARTS-admitted set, single VM, QUIET host, NO neighbour,
#               vCPUs pinned to distinct PHYSICAL cores (set PHYS_CORES).
#               Virtualization is the ONLY difference from bare metal.
#   predict   : miss ratio ~ 0; exec_us ~ target_c; any rare miss has steal_us
#               high and everything else ~0.
#   finding if: misses appear with steal_us~0 AND exec~target -> virtualization
#               breaks it via an un-instrumented path (timekeeping / IRQ-virt).
#
# Env you may override:
#   NODE        RT worker node (default from run_all.sh)
#   PHYS_CORES  cpuset of distinct physical cores, e.g. "0,2" (from cpu_topology.sh)
#   U_REGEX     taskset U filter (default: low/moderate U where it should hold)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

print_model "M1-ideal" \
    "rtdra, isolated, no neighbour, pinned to physical cores" \
    "miss~0; exec~target; rare miss => steal only" \
    "miss with steal~0 and exec~target (un-instrumented virtualization cause)"

export MODES="rtdra"
export INTERFERENCE="none"
export PER_JOB_ATTR="1"
export CPUSET="${PHYS_CORES:-}"                 # pin to distinct physical cores
export TASKSETS_DIR="$(filter_tasksets "/tmp/ts-m1" "${U_REGEX:-_U(0\.60|0\.80|1\.00)\.json}")"

run_model "m1-ideal"
