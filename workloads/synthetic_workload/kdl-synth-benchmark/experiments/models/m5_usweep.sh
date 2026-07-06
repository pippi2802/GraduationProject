#!/usr/bin/env bash
# M5 - WCET-TRANSFER & U-SWEEP: does a bare-metal budget stay valid, and where
# does the admitted set start to miss?  (the headline RQ1 plot; motivates RQ2)
#
#   condition : rtdra, bare-metal CARTS C/Q held FIXED, isolated/quiet host,
#               sweep admitted utilisation U across the FULL generated range.
#   predict   : miss ratio ~0 at low U, then rises SHARPLY past a critical U* <
#               the theoretical cap, because effective cloud capacity < nominal;
#               exec_us > target_c frequently (bare-metal C too small on cloud).
#   finding if: admitted sets stay miss-free up to the cap -> the guarantee
#               SURVIVES and bare-metal parameters transfer (null result, also
#               publishable).
#
# Output feeds a miss_ratio(U) curve; the knee is U*.  Env: none required.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

print_model "M5-usweep" \
    "rtdra, fixed bare-metal Q, isolated, U swept full range" \
    "miss~0 then sharp rise past U* < cap; exec>target common" \
    "miss-free up to the cap (guarantee survives; params transfer)"

export MODES="rtdra"
export INTERFERENCE="none"
export PER_JOB_ATTR="1"
export TASKSETS_DIR="$(filter_tasksets "/tmp/ts-m5" "")"   # all U

run_model "m5-usweep"

echo "# build the miss_ratio(U) curve with:" >&2
echo "#   python3 analysis/compare.py results/m5-usweep --out results/m5-usweep/curve.csv" >&2
