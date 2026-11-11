#!/usr/bin/env python3
"""check_round.py <model> [round] -- sanity-check one finished run in test-results/results.

Run from os-experiments/ (it reads workloads/ and test-results/ relative to this file).
Per cell: rows, median C vs calibrated target, deadline-miss rate, skipped releases, other files.
"""
import csv
import json
import pathlib
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
model = sys.argv[1]
rnd = sys.argv[2] if len(sys.argv) > 2 else "1"
ref = "model1" if model.endswith("model1") else "model5-phys"
tab = json.load(open(HERE / "workloads" / ref / "k_table.json"))
root = HERE / "test-results" / "results" / f"{model}_round{rnd}"
if not root.exists():
    sys.exit(f"missing {root}")

print(f"{'cell':12} {'rows':>5} {'medC_us':>9} {'target':>8} {'ratio':>6} {'miss%':>6} {'skipped':>7}  files")
for d in sorted(root.glob("*/U*")):
    key = f"{d.parent.name}-{d.name}"
    f = d / "jobs.csv"
    if not f.exists():
        print(f"{key:12} MISSING")
        continue
    rows = list(csv.DictReader(l for l in open(f) if not l.startswith("#")))
    if not rows:
        print(f"{key:12} EMPTY")
        continue
    cc = next((c for c in ("C_cputime_us", "C_us") if c in rows[0]), None)
    if cc is None:
        print(f"{key:12} columns: {list(rows[0])}")
        continue
    C = [float(r[cc]) for r in rows[6:]]                       # skip the 6 start-up jobs
    miss = sum(int(float(r["deadline_miss"])) for r in rows) / len(rows) * 100
    skip = sum(int(float(r.get("skipped_before") or 0)) for r in rows)
    med = statistics.median(C)
    tgt = tab[key]["median_C_us"]
    others = ",".join(p.name for p in d.iterdir() if p.name != "jobs.csv")
    flag = "" if 0.9 <= med / tgt <= 1.1 else "  <-- C off calibration"
    print(f"{key:12} {len(rows):5d} {med:9.0f} {tgt:8.0f} {med/tgt:6.2f} {miss:6.2f} {skip:7d}  {others}{flag}")
