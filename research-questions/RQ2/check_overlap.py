#!/usr/bin/env python3
"""Finds runs of different workloads that ran at the same time on the same node (they share the cores and the memory bandwidth: both runs are then not valid).

    python3 check_overlap.py workload3/validation_p3/iter0/run_validation.out workload1/validation_p3/iter0/run_validation.out [more logs]

Reads the log of each runner: a run starts at its "=== <run id>" line and ends at its "<run id> done" / "FAILED" line (a run that has not ended yet is open until now).
"""
import re, sys, datetime as dt

runs = []                                              # (log, scenario, run id, start, end)
for path in sys.argv[1:]:
    open_runs = {}
    for line in open(path, errors="replace"):
        m = re.match(r"\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\] (\w+): (.*)", line)
        if not m:
            continue
        t = dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ")
        scen, rest = m.group(2), m.group(3)
        s = re.match(r"=== (\S+)", rest)
        if s:
            open_runs[(scen, s.group(1))] = t
            continue
        e = re.match(r"(\S+) (done|FAILED)", rest)
        if e and (scen, e.group(1)) in open_runs:
            runs.append((path.split("/")[0], scen, e.group(1), open_runs.pop((scen, e.group(1))), t))
    now = dt.datetime.utcnow()
    for (scen, rid), t0 in open_runs.items():
        runs.append((path.split("/")[0], scen, rid, t0, now))

bad = 0
for i, a in enumerate(runs):
    for b in runs[i + 1:]:
        if a[0] != b[0] and a[1] == b[1] and a[3] < b[4] and b[3] < a[4]:      # other workload, same scenario (= same node), time windows overlap
            bad += 1
            print(f"OVERLAP on {a[1]}: {a[2]} ({a[3]:%H:%M}-{a[4]:%H:%M}) with {b[2]} ({b[3]:%H:%M}-{b[4]:%H:%M})")
print(f"{len(runs)} runs read, {bad} overlaps" + ("" if bad else ": none, the runs were not concurrent"))
