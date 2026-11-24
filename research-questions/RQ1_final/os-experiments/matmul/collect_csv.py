#!/usr/bin/env python3
"""
collect_csv.py [results_dir] [out_dir]

Builds, from test-results/results/<workload>_round<N>/<scale>/U<u>/jobs.csv, the
same one-file-per-(configuration, model) layout the frozen sieve data uses
(os-experiments/analysis/data/<cfg>-<model>.csv, kubedeadline-experiments/analysis/data/
model1.csv and model5-phys.csv), so results_final/make_results_final.py can read it.

Every output row is a job row of jobs.csv plus the columns  scenario, workload,
round, scale, U  (U is the nominal label of the cell, e.g. 0.1; the effective U is in
k_table.json).  '#' comment lines of jobs.csv are skipped.

Also prints a completeness table: rounds found per (configuration, model) and cells per round.
"""
import csv
import pathlib
import re
import sys
from collections import defaultdict

RES = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "test-results/results")
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "collected")
PAT = re.compile(r"^(?:(\d\d)-)?(model1|model5(?:-phys)?)_round(\d+)$")
CELLS = {"full": 8, "07": 6, "01": 6}      # cells per model and round (01 and 07 skip U0.94)

OUT.mkdir(parents=True, exist_ok=True)
groups = defaultdict(list)                 # (cfg, model file stem) -> [(round, dir)]
for d in sorted(RES.iterdir()):
    m = PAT.match(d.name)
    if m and d.is_dir():
        cfg = m.group(1) or "full"
        groups[(cfg, m.group(2))].append((int(m.group(3)), d))

summary = []
for (cfg, model), items in sorted(groups.items()):
    stem = model if cfg == "full" else f"{cfg}-{model}"
    path = OUT / f"{stem}.csv"
    header = None
    rows_total = 0
    per_round = {}
    with open(path, "w", newline="") as out:
        w = csv.writer(out)
        for rnd, d in sorted(items):
            ncell = 0
            for f in sorted(d.glob("*/U*/jobs.csv")):
                scale, u = f.parent.parent.name, float(f.parent.name[1:])
                with open(f) as fh:
                    hdr = None
                    for line in fh:
                        if line.startswith("#"):
                            continue
                        p = line.rstrip("\n").split(",")
                        if hdr is None:
                            hdr = p
                            if header is None:
                                header = p
                                w.writerow(p + ["scenario", "workload", "round", "scale", "U"])
                            elif p != header:
                                sys.exit(f"header mismatch in {f}")
                            continue
                        w.writerow(p + [cfg, model, rnd, scale, f"{u:g}"])
                        rows_total += 1
                ncell += 1
            per_round[rnd] = ncell
    want = CELLS.get(cfg, 8)
    bad = {r: n for r, n in per_round.items() if n != want}
    summary.append((stem, sorted(per_round), want, bad, rows_total))

print(f"{'file':<18}{'rounds':<26}{'rows':>10}  incomplete rounds (cells/want)")
for stem, rounds, want, bad, rows in summary:
    print(f"{stem + '.csv':<18}{','.join(map(str, rounds)):<26}{rows:>10}  "
          + (", ".join(f"r{r}:{n}/{want}" for r, n in sorted(bad.items())) or "-"))
print(f"\nwritten to {OUT}/")
