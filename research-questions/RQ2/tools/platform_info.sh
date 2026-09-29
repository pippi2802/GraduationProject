#!/usr/bin/env bash
# platform_info.sh - record platform facts needed to interpret RQ2 results
# (CPU model, topology, LLC size, kernel) into JSON, and patch
# configs/platform.yaml's llc_size_kb field so downstream stages (e.g. enemy
# presets) can read a single source of truth.
#
# Usage: platform_info.sh [--output results/derived/platform/platform_info.json]
#                          [--platform-yaml configs/platform.yaml]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RQ2_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT="$RQ2_ROOT/results/derived/platform/platform_info.json"
PLATFORM_YAML="$RQ2_ROOT/configs/platform.yaml"

while [ $# -gt 0 ]; do
    case "$1" in
        --output) OUTPUT="$2"; shift 2 ;;
        --platform-yaml) PLATFORM_YAML="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

mkdir -p "$(dirname "$OUTPUT")"

LSCPU_JSON="{}"
if command -v lscpu >/dev/null 2>&1; then
    if lscpu --json >/dev/null 2>&1; then
        LSCPU_JSON="$(lscpu --json)"
    fi
fi

CPU_MODEL="$(awk -F': ' '/^model name/{print $2; exit}' /proc/cpuinfo 2>/dev/null || true)"
THREADS_PER_CORE="$(lscpu 2>/dev/null | awk -F': +' '/^Thread\(s\) per core/{print $2}')"
KERNEL_VERSION="$(uname -r)"
KERNEL_CMDLINE="$(cat /proc/cmdline 2>/dev/null || true)"

# LLC size: prefer the last-level cache reported by lscpu (L3 on most x86,
# falls back to the highest-numbered cache if there's no L3 line).
LLC_SIZE_KB=""
if command -v lscpu >/dev/null 2>&1; then
    LLC_LINE="$(lscpu 2>/dev/null | grep -E '^L3 cache' || true)"
    if [ -z "$LLC_LINE" ]; then
        LLC_LINE="$(lscpu 2>/dev/null | grep -E '^L2 cache' || true)"
    fi
    if [ -n "$LLC_LINE" ]; then
        RAW="$(echo "$LLC_LINE" | awk -F': +' '{print $2}')"
        # lscpu prints e.g. "32 MiB" or "32768K"; normalize to KB (integer)
        NUM="$(echo "$RAW" | grep -oE '[0-9]+(\.[0-9]+)?' | head -1)"
        if echo "$RAW" | grep -qi 'mib\|mb'; then
            LLC_SIZE_KB=$(awk -v n="$NUM" 'BEGIN{printf "%d", n*1024}')
        elif echo "$RAW" | grep -qi 'kib\|kb\|k'; then
            LLC_SIZE_KB=$(awk -v n="$NUM" 'BEGIN{printf "%d", n}')
        fi
    fi
fi

VM_METADATA="null"
if command -v curl >/dev/null 2>&1; then
    VM_METADATA="$(curl -s -H "Metadata:true" --max-time 2 \
        "http://169.254.169.254/metadata/instance?api-version=2021-02-01" 2>/dev/null || echo null)"
    if [ -z "$VM_METADATA" ]; then
        VM_METADATA="null"
    fi
fi

python3 - "$OUTPUT" "$LSCPU_JSON" "$CPU_MODEL" "$THREADS_PER_CORE" \
    "$KERNEL_VERSION" "$KERNEL_CMDLINE" "$LLC_SIZE_KB" "$VM_METADATA" <<'PYEOF'
import json
import sys
import datetime

(output, lscpu_json, cpu_model, threads_per_core, kernel_version,
 kernel_cmdline, llc_size_kb, vm_metadata) = sys.argv[1:9]

try:
    lscpu = json.loads(lscpu_json) if lscpu_json.strip() else {}
except json.JSONDecodeError:
    lscpu = {}

try:
    vm = json.loads(vm_metadata) if vm_metadata.strip() else None
except json.JSONDecodeError:
    vm = None

info = {
    "captured_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "cpu_model": cpu_model or None,
    "threads_per_core": threads_per_core or None,
    "kernel_version": kernel_version or None,
    "kernel_cmdline": kernel_cmdline or None,
    "llc_size_kb": int(llc_size_kb) if llc_size_kb.strip().isdigit() else None,
    "lscpu": lscpu,
    "vm_metadata": vm,
}
with open(output, "w") as f:
    json.dump(info, f, indent=2)
print(f"wrote {output}")
print(json.dumps(info, indent=2))
PYEOF

# Patch configs/platform.yaml's llc_size_kb in place (create the key if
# missing), without requiring PyYAML for this one field.
if [ -f "$PLATFORM_YAML" ] && [ -n "$LLC_SIZE_KB" ]; then
    python3 - "$PLATFORM_YAML" "$LLC_SIZE_KB" <<'PYEOF'
import sys

path, llc_kb = sys.argv[1], sys.argv[2]
with open(path) as f:
    lines = f.readlines()

found = False
for i, line in enumerate(lines):
    if line.strip().startswith("llc_size_kb:"):
        lines[i] = f"llc_size_kb: {llc_kb}\n"
        found = True
        break
if not found:
    lines.append(f"llc_size_kb: {llc_kb}\n")

with open(path, "w") as f:
    f.writelines(lines)
print(f"updated {path}: llc_size_kb={llc_kb}")
PYEOF
fi
