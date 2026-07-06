#!/usr/bin/env bash
# Run ONLY the tight (tens-of-ms, P=10ms) cells. Fast (~2 min/cell).
# Results land in results/<timeblock>/tens-of-ms/U*/ as each cell completes.
#
# Usage:
#   ./run_tight.sh                       # auto timeblock label
#   ./run_tight.sh tb-mylabel            # explicit timeblock
#   ./run_tight.sh tb-mylabel --only-u 0.9 0.95   # subset / extra flags passed through
set -euo pipefail
cd "$(dirname "$0")"
TB="${1:-tb-$(date +%Y%m%d-%H%M)}"
shift || true
exec python3 run_model1.py --timeblock "$TB" --scales tight "$@"
