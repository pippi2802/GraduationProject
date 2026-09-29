#!/usr/bin/env python3
"""Budget-risk curve: replay a measured cpu_ns trace under a hard CBS budget Q.

For each candidate Q (deadline == period, skip semantics): a job with cpu
time c needs n = ceil(c/Q) server periods. n==1 -> met. n>1 -> this job AND
the next (n-1) activations are missed/skipped. Waiting time is ignored -
this predicts CPU-only interference from the reservation, not scheduling
delay, so a tolerance can be applied to the resulting curve after the fact.
"""
import argparse
import csv
import math

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from metrics import mk_worst, max_consecutive_misses


def replay_trace(cpu_ns, q_ns):
    n = len(cpu_ns)
    miss = np.zeros(n, dtype=bool)
    skip_until = 0
    for i in range(n):
        if i < skip_until:
            miss[i] = True
            continue
        jobs_needed = math.ceil(cpu_ns[i] / q_ns) if cpu_ns[i] > 0 else 1
        if jobs_needed <= 1:
            miss[i] = False
        else:
            miss[i] = True
            skip_until = i + jobs_needed
    return miss


def load_cpu_ns(path):
    with open(path, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("warmup", "0") != "1"]
    rows.sort(key=lambda r: int(r["job_id"]))
    return np.array([int(r["cpu_ns"]) for r in rows if r["cpu_ns"] != ""], dtype=np.float64)


def q_grid(args):
    if args.q_list:
        return [q * 1e6 for q in args.q_list]
    return list(np.linspace(args.q_min_ms * 1e6, args.q_max_ms * 1e6, args.q_steps))


def evaluate(cpu_ns, period_ns, q_values, k_values):
    results = []
    for q_ns in q_values:
        miss = replay_trace(cpu_ns, q_ns)
        row = {
            "q_ms": q_ns / 1e6,
            "bandwidth": q_ns / period_ns,
            "miss_rate": float(np.mean(miss)),
            "max_consecutive_misses": max_consecutive_misses(miss),
        }
        for k in k_values:
            row[f"mk_{k}"] = mk_worst(miss, k)
        results.append(row)
    return results


def select_smallest_q(results, target_miss_rate, max_consecutive, mk_constraint):
    for row in sorted(results, key=lambda r: r["q_ms"]):
        if target_miss_rate is not None and row["miss_rate"] > target_miss_rate:
            continue
        if max_consecutive is not None and row["max_consecutive_misses"] > max_consecutive:
            continue
        if mk_constraint is not None:
            m, k = mk_constraint
            worst = row.get(f"mk_{k}")
            if worst is None or worst < m:
                continue
        return row
    return None


def selftest():
    cpu = np.array([5.0, 25.0, 5.0, 5.0, 5.0], dtype=np.float64) * 1e6  # ns
    miss = replay_trace(cpu, q_ns=10e6)  # job[1] needs ceil(25/10)=3 -> misses jobs 1,2,3
    assert list(miss) == [False, True, True, True, False], miss
    print("selftest OK")


def main():
    p = argparse.ArgumentParser(description="Budget-risk curve from a measured cpu_ns trace")
    p.add_argument("csv", nargs="?", help="one instance's rt_video.py CSV")
    p.add_argument("--period-ms", type=float)
    p.add_argument("--q-min-ms", type=float)
    p.add_argument("--q-max-ms", type=float)
    p.add_argument("--q-steps", type=int, default=30)
    p.add_argument("--q-list", type=float, nargs="+")
    p.add_argument("--k", type=int, nargs="+", default=[50, 100])
    p.add_argument("--output", default="replay.csv")
    p.add_argument("--plot", default="replay.png")
    p.add_argument("--target-miss-rate", type=float)
    p.add_argument("--max-consecutive", type=int)
    p.add_argument("--mk", type=str, help="m,k constraint, e.g. 45,50")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()

    if args.selftest:
        selftest()
        if not args.csv:
            return

    cpu_ns = load_cpu_ns(args.csv)
    period_ns = args.period_ms * 1e6
    results = evaluate(cpu_ns, period_ns, q_grid(args), args.k)

    with open(args.output, "w", newline="") as f:
        fieldnames = list(results[0].keys())
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)

    bw = [r["bandwidth"] for r in results]
    mr = [max(r["miss_rate"], 1e-6) for r in results]  # log axis can't show 0
    plt.figure()
    plt.plot(bw, mr, marker="o")
    plt.yscale("log")
    plt.xlabel("bandwidth Q/P")
    plt.ylabel("predicted miss rate")
    plt.title("Budget-risk curve")
    plt.grid(True, which="both", alpha=0.3)
    plt.savefig(args.plot)

    mk_constraint = None
    if args.mk:
        m, k = args.mk.split(",")
        mk_constraint = (int(m), int(k))
    if args.target_miss_rate is not None or args.max_consecutive is not None or mk_constraint is not None:
        chosen = select_smallest_q(results, args.target_miss_rate, args.max_consecutive, mk_constraint)
        print("smallest Q satisfying constraints:", chosen)


if __name__ == "__main__":
    main()
