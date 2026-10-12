#!/usr/bin/env bash
# Runs the online validation (procedure 2) of the audio workload and then of the segmentation workload, unattended, one after the other
# (they use the same two nodes, so they cannot run together). Each part is safe to restart: a collected run is skipped.
#
#   DRY_RUN=1 ./run_validation_p2_all.sh            # the plan of both, touches nothing
#   nohup ./run_validation_p2_all.sh > run_validation_p2_all.out 2>&1 &
#   ITER=1 nohup ./run_validation_p2_all.sh ...      # after a recalibration, once validation_p2/iter1/ exists
#   ONLY="workload3" ...                              # only one of them (workload3 = audio, workload2 = segmentation)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITER="${ITER:-0}"
ONLY="${ONLY:-workload3 workload2}"
status=0
for wl in $ONLY; do
    d="$HERE/$wl/validation_p2/iter$ITER"
    [ -x "$d/run_validation.sh" ] || { echo "[$(date -u +%FT%TZ)] $wl: no $d/run_validation.sh, skipped"; status=1; continue; }
    echo "[$(date -u +%FT%TZ)] $wl: start (iter $ITER)"
    ( cd "$d" && ./run_validation.sh > run_validation.out 2>&1 )
    rc=$?
    echo "[$(date -u +%FT%TZ)] $wl: finished, exit $rc (see $d/run_validation.out and results/*/summary.tsv)"
    [ "$rc" = 0 ] || status=1
done
exit $status
