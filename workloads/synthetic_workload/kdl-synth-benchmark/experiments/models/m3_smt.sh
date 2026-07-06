#!/usr/bin/env bash
# M3 - SMT: does CARTS's "physical core" assumption break on vCPUs?
#
#   condition : SAME admitted set, SAME U, two arms differing only in vCPU->core
#               mapping: pinned to HYPERTHREAD SIBLINGS vs to distinct PHYSICAL
#               cores. Run under CFS (vanilla) so pinning is clean and fully
#               controlled; the effect (throughput per vCPU) is a hardware
#               property that then applies to rtdra's reserved cores.
#   predict   : siblings arm -> exec_us inflates ~20-50% > target_c -> overrun
#               -> misses with steal_us~0; physical arm removes them.
#   finding if: physical arm STILL misses at that U -> SMT was not the cause;
#               the capacity gap is elsewhere.
#
# Required env (from scripts/cpu_topology.sh):
#   SIBLING_CPUS   two sibling threads of ONE physical core, e.g. "0,4"
#   PHYSICAL_CPUS  one thread each of TWO physical cores, e.g. "0,1"
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

: "${SIBLING_CPUS:?set SIBLING_CPUS, e.g. 0,4  (see scripts/cpu_topology.sh)}"
: "${PHYSICAL_CPUS:?set PHYSICAL_CPUS, e.g. 0,1 (see scripts/cpu_topology.sh)}"

print_model "M3-smt" \
    "same set/U; CFS pinned to siblings (${SIBLING_CPUS}) vs physical (${PHYSICAL_CPUS})" \
    "siblings: exec inflates, overrun, misses (steal~0); physical: clean" \
    "physical arm still misses (SMT not the cause)"

export MODES="${MODES:-vanilla}"               # CFS: clean, controlled pinning
export INTERFERENCE="none"
export PER_JOB_ATTR="1"
export TASKSETS_DIR="$(filter_tasksets "/tmp/ts-m3" "${U_REGEX:-_U(1\.20|1\.40)\.json}")"

echo "### arm: SIBLINGS (${SIBLING_CPUS})" >&2
CPUSET="${SIBLING_CPUS}" run_model "m3-smt/siblings"

echo "### arm: PHYSICAL (${PHYSICAL_CPUS})" >&2
CPUSET="${PHYSICAL_CPUS}" run_model "m3-smt/physical"
