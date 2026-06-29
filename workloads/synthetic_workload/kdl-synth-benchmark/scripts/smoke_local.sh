#!/usr/bin/env bash
# Compile the workload in Linux (WSL) and run a short smoke test, then validate
# the JSONL output. No cluster required. Catches compile + runtime errors.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/workload"

echo "=== building rt-workload ==="
make clean >/dev/null 2>&1 || true
make

TS=$(ls "$ROOT"/gen/tasksets/*.json | head -n1)
echo "=== running smoke test on: $(basename "$TS") ==="
OUT="$(mktemp)"

./rt-workload \
    --taskset "$TS" \
    --jobs 100 --warmup 5 \
    --out "$OUT" \
    --run-id smoke-test --taskset-id smoke \
    --mode vanilla --cores-m 2 --util 1.0 \
    --interference none --node wsl --kernel cfs

echo "=== validating output ==="
LINES=$(wc -l < "$OUT")
echo "metrics lines: $LINES"
echo "--- first record ---"
head -n1 "$OUT"
echo "--- last record ---"
tail -n1 "$OUT"

python3 - "$OUT" <<'PY'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
assert rows, "no records!"
keys = {"run_id","mode","task_id","job_index","exec_time_us","response_time_us",
        "deadline_miss","tardiness_us","period_t_us","util"}
missing = keys - rows[0].keys()
assert not missing, f"missing keys: {missing}"
execs = [r["exec_time_us"] for r in rows]
resp  = [r["response_time_us"] for r in rows]
miss  = sum(1 for r in rows if r["deadline_miss"])
print(f"records           : {len(rows)}")
print(f"exec_us  min/avg/max: {min(execs)}/{sum(execs)//len(execs)}/{max(execs)}")
print(f"resp_us  min/avg/max: {min(resp)}/{sum(resp)//len(resp)}/{max(resp)}")
print(f"deadline misses    : {miss}/{len(rows)}")
print("OK: JSONL well-formed and schema valid")
PY

rm -f "$OUT"
echo "=== smoke test PASSED ==="
