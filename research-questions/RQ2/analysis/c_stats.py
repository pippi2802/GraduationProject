#!/usr/bin/env python3
"""C and execution-time statistics of one or more result CSVs, and the period they ask for. Standard library only.

    python3 c_stats.py ../workload2/results/single_core/pilot/instance0.csv [more.csv ...]

C = cpu_ns, the CPU time of a job (ms).  E = end_ns - start_ns, its execution time on the wall clock (ms): C plus the time the job was not on its CPU
(throttled by its reservation, preempted).  The table shows, for candidate periods T, how much of T the task uses.
Rules of thumb used in this project: the median of C at 30-50% of T, the worst job (also under stress) clearly below T. T is then yours to choose."""
import csv, statistics as st, sys

if len(sys.argv) < 2:
    sys.exit(__doc__)
rows = [r for f in sys.argv[1:] for r in csv.DictReader(open(f)) if r["cpu_ns"] and r["end_ns"]]
C = sorted(int(r["cpu_ns"]) / 1e6 for r in rows)
E = sorted((int(r["end_ns"]) - int(r["start_ns"])) / 1e6 for r in rows)
D = sorted(max(0, int(r["end_ns"]) - int(r["start_ns"]) - int(r["cpu_ns"])) / 1e6 for r in rows)      # time off the CPU
q = lambda x, p: x[min(len(x) - 1, int(p * len(x)))]
line = lambda name, x: print(f"{name:<24} min {x[0]:7.2f}  median {st.median(x):7.2f}  mean {st.mean(x):7.2f}  p90 {q(x, .9):7.2f}  p99 {q(x, .99):7.2f}  p99.9 {q(x, .999):7.2f}  max {x[-1]:7.2f}   cv {st.stdev(x) / st.mean(x):.3f}")
print(f"n = {len(C)} jobs (ms)")
line("C  (CPU time)", C)
line("E  (execution time)", E)
line("E - C (off the CPU)", D)
if len(C) < 10000:
    print(f"(p99.9 rests on {max(1, int(len(C) * .001))} job(s) and the max is one job: more jobs give a tail you can trust)")
med, p999, mx, emax = st.median(C), q(C, .999), C[-1], E[-1]
need = {"median C at 40% of T": med / 0.40, "p99.9 of C at 60% of T": p999 / 0.60, "worst E at 80% of T": emax / 0.80}
print("\nperiod needed:  " + "   ".join(f"{k}: {v:.3g} ms" for k, v in need.items()))
base = max(need.values())
print(f"=> the largest of these, T of about {base:.3g} ms, satisfies all three\n")
print(f"{'T (ms)':>7} {'median C/T':>11} {'p99.9 C/T':>10} {'max C/T':>8} {'median E/T':>11} {'max E/T':>8}")
for T in sorted({float(f"{v:.2g}") for v in (med / .5, med / .4, med / .3, base)} - {0.0}):          # two significant digits, any scale
    print(f"{T:7g} {med / T:11.0%} {p999 / T:10.0%} {mx / T:8.0%} {st.median(E) / T:11.0%} {emax / T:8.0%}")
