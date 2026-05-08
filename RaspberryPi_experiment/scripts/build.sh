#!/usr/bin/env bash
# Build the periodic workload natively on the Pi.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
gcc -O2 -Wall -pthread -o rt_multi_periodic rt_multi_periodic.c
echo "built: $ROOT_DIR/rt_multi_periodic"
