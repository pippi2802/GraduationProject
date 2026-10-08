#!/usr/bin/env python3
"""C statistics of one or more result CSVs, and the period they ask for. Standard library only.

    python3 c_stats.py ../workload2/results/single_core/pilot/instance0.csv [more.csv ...]

C = cpu_ns of the executed jobs, in ms. The table shows, for candidate periods T, how much of T the task uses at its median, p99.9 and worst job.
Rules of thumb used in this project: the median at 30-50% of T, the worst job (also under stress) clearly below T. T is then yours to choose."""
import csv, statistics as st, sys

if len(sys.argv) < 2:
    sys.exit(__doc__)
x = sorted(int(r["cpu_ns"]) / 1e6 for f in sys.argv[1:] for r in csv.DictReader(open(f)) if r["cpu_ns"])
q = lambda p: x[min(len(x) - 1, int(p * len(x)))]
med, p99, p999, mx = st.median(x), q(.99), q(.999), x[-1]
print(f"n={len(x)} jobs   C (ms): min {x[0]:.1f}  median {med:.1f}  mean {st.mean(x):.1f}  p90 {q(.9):.1f}  p99 {p99:.1f}  p99.9 {p999:.1f}  max {mx:.1f}   cv {st.stdev(x) / st.mean(x):.3f}")
if len(x) < 5000:
    print(f"(only {len(x)} jobs: p99.9 and max are single jobs; use 3000 or more for a tail you can trust)")
need = {"median at 40% of T": med / 0.40, "p99.9 at 60% of T": p999 / 0.60, "worst job at 80% of T": mx / 0.80}
print("\nperiod needed:  " + "   ".join(f"{k}: {v:.0f} ms" for k, v in need.items()))
base = max(need.values())
print(f"=> the largest of these, T of about {base:.0f} ms, satisfies all three\n")
print(f"{'T (ms)':>7} {'median/T':>9} {'p99.9/T':>8} {'max/T':>7}")
for T in sorted({float(f"{v:.2g}") for v in (med / .5, med / .4, med / .3, base)} - {0.0}):          # two significant digits, any scale
    print(f"{T:7g} {med / T:9.0%} {p999 / T:8.0%} {mx / T:7.0%}")
