#!/usr/bin/env bash
# Runs the online validation of procedure 3 (the relaxed and strict levels) of the audio, video and segmentation workloads, unattended, one after the other
# (they use the same two nodes, so they cannot run together). Each part is safe to restart: a collected run is skipped.
#
#   DRY_RUN=1 ./run_validation_p3_all.sh              # the plan of all three, touches nothing
#   nohup ./run_validation_p3_all.sh > run_validation_p3_all.out 2>&1 &
#   ONLY="workload3" ./run_validation_p3_all.sh        # only one (workload3 = audio, workload1 = video, workload2 = segmentation)
#
# Audio 16 runs (about 1.4 h), video 8 runs (about 1.6 h), segmentation 4 runs (about 2.4 h): about 5.5 h in total.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ITER="${ITER:-0}"
ONLY="${ONLY:-workload3 workload1 workload2}"
status=0
for wl in $ONLY; do
    d="$HERE/$wl/validation_p3/iter$ITER"
    [ -x "$d/run_validation.sh" ] || { echo "[$(date -u +%FT%TZ)] $wl: no $d/run_validation.sh, skipped"; status=1; continue; }
    echo "[$(date -u +%FT%TZ)] $wl: start (iter $ITER)"
    ( cd "$d" && ./run_validation.sh > run_validation.out 2>&1 )
    rc=$?
    echo "[$(date -u +%FT%TZ)] $wl: finished, exit $rc (see $d/run_validation.out and results/logs/ or results/*/summary.tsv)"
    [ "$rc" = 0 ] || status=1
done
exit $status
