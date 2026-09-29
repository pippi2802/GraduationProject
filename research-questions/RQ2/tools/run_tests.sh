#!/usr/bin/env bash
# run_tests.sh - the test-of-the-tests wrapper: builds the native
# enemy/victim binaries (tests/test_enemy.py and tests/test_victim.py exec
# them directly) then runs the full pytest suite. `make test` calls this.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RQ2_ROOT="$(dirname "$SCRIPT_DIR")"

echo "== building stress/enemy and stress/victim =="
make -C "$RQ2_ROOT/stress"

echo "== running pytest =="
cd "$RQ2_ROOT"
python3 -m pytest tests/ -v "$@"
