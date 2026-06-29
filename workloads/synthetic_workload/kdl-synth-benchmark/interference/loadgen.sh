#!/bin/sh
# Best-effort noisy-neighbour load generator.
# CPU pressure (and optional memory-bandwidth pressure) via stress-ng.
# All knobs come from environment variables so the pod template can set them.
set -eu

CPU_WORKERS="${CPU_WORKERS:-4}"     # number of CPU stressors
CPU_LOAD="${CPU_LOAD:-100}"         # % load per CPU stressor
VM_WORKERS="${VM_WORKERS:-0}"       # memory-bandwidth stressors (0 = off)
VM_BYTES="${VM_BYTES:-256M}"        # per-vm-worker allocation
TIMEOUT="${TIMEOUT:-0}"             # seconds; 0 = run until killed

ARGS="--cpu ${CPU_WORKERS} --cpu-load ${CPU_LOAD}"

if [ "${VM_WORKERS}" -gt 0 ]; then
    ARGS="${ARGS} --vm ${VM_WORKERS} --vm-bytes ${VM_BYTES}"
fi

if [ "${TIMEOUT}" -gt 0 ]; then
    ARGS="${ARGS} --timeout ${TIMEOUT}"
fi

echo "interference: stress-ng ${ARGS}"
# exec so SIGTERM from kubectl delete reaches stress-ng directly.
exec stress-ng ${ARGS} --metrics-brief
