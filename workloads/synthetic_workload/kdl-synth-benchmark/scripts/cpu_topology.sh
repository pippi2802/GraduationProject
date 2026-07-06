#!/usr/bin/env bash
# Print the CPU topology of the RT worker node so M3/M4 can pick a SIBLING pair
# (two hyperthreads of ONE physical core) and a PHYSICAL pair (one thread each
# of TWO physical cores).
#
# Run this ON the RT worker node (ssh in first). It reads
# /sys/devices/system/cpu/cpuN/topology/thread_siblings_list.
#
# Example output on a 4-vCPU D4s_v5 (2 cores x 2 threads):
#   core 0 -> threads 0,2
#   core 1 -> threads 1,3
#   SUGGESTED  SIBLING_CPUS=0,2   PHYSICAL_CPUS=0,1
set -euo pipefail

declare -A seen
sib_pair=""
phys_list=""

for d in /sys/devices/system/cpu/cpu[0-9]*; do
    cpu="${d##*/cpu}"
    sl_file="${d}/topology/thread_siblings_list"
    [ -r "${sl_file}" ] || continue
    sl="$(cat "${sl_file}")"                     # e.g. "0,2" or "0-1"
    key="${sl}"
    if [ -z "${seen[$key]:-}" ]; then
        seen[$key]=1
        echo "core (siblings ${sl})"
        # first physical thread of this core -> physical set
        first="${sl%%[,-]*}"
        phys_list="${phys_list:+${phys_list},}${first}"
        # first core that actually has 2+ siblings -> sibling set
        if [ -z "${sib_pair}" ] && printf '%s' "${sl}" | grep -q '[,-]'; then
            sib_pair="$(printf '%s' "${sl}" | tr '-' ',')"
        fi
    fi
done

# Trim the physical set to two cores (enough for m<=2 task sets in this bench).
phys_pair="$(printf '%s' "${phys_list}" | cut -d, -f1,2)"

echo
echo "SUGGESTED for M3/M4 (m<=2):"
echo "  export SIBLING_CPUS=${sib_pair:-<none: SMT disabled?>}"
echo "  export PHYSICAL_CPUS=${phys_pair}"
echo "  export PINNED_CPUS=${phys_pair}"
