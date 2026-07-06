#!/usr/bin/env bash
# Run ONLY the soft (hundreds-of-ms, P=100ms) cells. Slow (~18 min/cell @ 10k jobs).
# Results land in results/<timeblock>/hundreds-of-ms/U*/ as each cell completes.
#
# Usage:
#   ./run_soft.sh                        # auto timeblock label
#   ./run_soft.sh tb-mylabel             # explicit timeblock
#   ./run_soft.sh tb-mylabel --only-u 0.8 0.9 0.95
set -euo pipefail
cd "$(dirname "$0")"
TB="${1:-tb-$(date +%Y%m%d-%H%M)}"
shift || true
exec python3 run_model1.py --timeblock "$TB" --scales soft "$@"
