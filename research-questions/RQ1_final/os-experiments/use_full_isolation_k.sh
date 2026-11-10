#!/usr/bin/env bash
# use_full_isolation_k.sh -- one calibration for all of RQ1.
#
# Every configuration (01..08) uses the K table of the full-isolation runs:
#   single-core: workloads/model1       -> workloads/NN-model1/k_table.json
#   multi-core : workloads/model5-phys  -> workloads/NN-model5/k_table.json
# and its manifests are regenerated from it (generate_yaml.py). Budget Q = U * P
# and the period do not come from the table, so only K changes.
#
#   ./use_full_isolation_k.sh          # apply
#   ./use_full_isolation_k.sh --dry    # only list which tables differ
set -euo pipefail
cd "$(dirname "$0")"
DRY=0; [ "${1:-}" = "--dry" ] && DRY=1

for p in 1 5; do
  ref=model1; [ "$p" = 5 ] && ref=model5-phys
  [ -f "workloads/$ref/k_table.json" ] || { echo "missing workloads/$ref/k_table.json"; exit 1; }
  # the reference itself: its manifests must also come from its own (new) table
  if [ "$DRY" = 0 ]; then echo "$ref: regenerate from its own table"; python3 generate_yaml.py "$ref" | tail -1; fi
  for d in workloads/[0-9][0-9]-model$p; do
    n=$(basename "$d")
    if cmp -s "workloads/$ref/k_table.json" "$d/k_table.json"; then
      echo "$n: already identical to $ref"; continue
    fi
    echo "$n: differs from $ref"
    [ "$DRY" = 1 ] && continue
    cp "workloads/$ref/k_table.json" "$d/k_table.json"
    python3 generate_yaml.py "$n" | tail -1
  done
done
