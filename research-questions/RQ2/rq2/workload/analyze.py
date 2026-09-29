#!/usr/bin/env python3
"""Analyze rt_video.py CSV logs: per-instance + aggregated timing report.

Sequence metrics ((m,k), consecutive misses, burstiness) are computed PER
INSTANCE and never mixed across instances/CSVs, since they depend on job
order within one task's own schedule.
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from rq2.common.metrics import mk_worst, max_consecutive_misses, burstiness_index  # noqa: E402


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else float("nan")


def load_rows(paths):
    rows = []
    for path in paths:
        with open(path, newline="") as f:
            rows.extend(csv.DictReader(f))
    return rows


def analyze_instance(rows, k_values):
    rows = sorted(rows, key=lambda r: int(r["job_id"]))
    skipped = np.array([r["skipped"] == "1" for r in rows])
    deadline_met = np.array([r["deadline_met"] == "1" for r in rows])
    miss = ~deadline_met  # skipped rows already have deadline_met=0

    ok = ~skipped
    response_ns = np.array([int(r["response_ns"]) for r in rows if r["response_ns"] != ""])
    cpu_ns = np.array([int(r["cpu_ns"]) for r in rows if r["cpu_ns"] != ""])
    wait_ns = np.array([int(r["wait_ns"]) for r in rows if r["wait_ns"] != ""])
    period_ns = None
    if len(rows) >= 2:
        rel = [int(r["release_ns"]) for r in rows[:2]]
        period_ns = rel[1] - rel[0]

    result = {
        "n_activations": len(rows),
        "miss_rate_pct": 100.0 * float(np.mean(miss)) if len(miss) else float("nan"),
        "response_ns": {
            "median": pct(response_ns, 50), "p99": pct(response_ns, 99), "p99.9": pct(response_ns, 99.9),
            "max": float(np.max(response_ns)) if len(response_ns) else float("nan"),
        },
        "cpu_ns": {
            "median": pct(cpu_ns, 50), "p90": pct(cpu_ns, 90), "p99": pct(cpu_ns, 99),
            "p99.9": pct(cpu_ns, 99.9), "p99.99": pct(cpu_ns, 99.99),
            "max": float(np.max(cpu_ns)) if len(cpu_ns) else float("nan"),
            "cv": float(np.std(cpu_ns) / np.mean(cpu_ns)) if len(cpu_ns) and np.mean(cpu_ns) > 0 else float("nan"),
        },
        "wait_ns": {
            "mean": float(np.mean(wait_ns)) if len(wait_ns) else float("nan"),
            "p99": pct(wait_ns, 99), "max": float(np.max(wait_ns)) if len(wait_ns) else float("nan"),
        },
        "max_consecutive_misses": max_consecutive_misses(miss),
        "mk": {}, "burstiness": {},
    }
    if len(response_ns):
        med = result["response_ns"]["median"]
        result["response_ns"]["max_over_median"] = float(np.max(response_ns)) / med if med > 0 else float("nan")
    if period_ns:
        max_resp = np.max(response_ns) if len(response_ns) else 0
        result["worst_lateness_periods"] = (float(max_resp) - period_ns) / period_ns

    for k in k_values:
        result["mk"][str(k)] = mk_worst(miss, k)
        result["burstiness"][str(k)] = burstiness_index(miss, k)
    return result


def read_steal_time(meta_paths):
    """cpu 'steal' jiffies delta between run start/end, if metadata has it."""
    out = {}
    for path in meta_paths:
        try:
            with open(path) as f:
                meta = json.load(f)
        except OSError:
            continue
        s0, s1 = meta.get("proc_stat_cpu_start"), meta.get("proc_stat_cpu_end")
        if not s0 or not s1:
            continue
        f0, f1 = s0.split()[1:], s1.split()[1:]
        if len(f0) >= 8 and len(f1) >= 8:
            out[meta["instance_id"]] = int(f1[7]) - int(f0[7])  # field 8 = steal
    return out


def selftest():
    miss = np.array([False] * 45 + [True] * 5 + [False] * 50)  # 100 activations, 5 consecutive misses
    assert mk_worst(miss, 50) == 45, mk_worst(miss, 50)
    assert max_consecutive_misses(miss) == 5, max_consecutive_misses(miss)
    b = burstiness_index(miss, 50)
    expected = (50 - 45) / (50 * (5 / 100))
    assert abs(b - expected) < 1e-9, (b, expected)
    no_miss = np.array([False] * 100)
    assert burstiness_index(no_miss, 50) is None
    print("selftest OK")


def main():
    p = argparse.ArgumentParser(description="Analyze rt_video.py CSV logs")
    p.add_argument("csvs", nargs="*")
    p.add_argument("--meta", nargs="*", default=[], help="matching .meta.json files, for steal time")
    p.add_argument("--k", type=int, nargs="+", default=[50, 100])
    p.add_argument("--output", default="analysis.json")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()

    if args.selftest:
        selftest()
        if not args.csvs:
            return

    rows = load_rows(args.csvs)
    rows = [r for r in rows if r.get("warmup", "0") != "1"]
    by_instance = defaultdict(list)
    for r in rows:
        by_instance[r["instance_id"]].append(r)

    steal = read_steal_time(args.meta)
    per_instance = {}
    for instance_id, inst_rows in by_instance.items():
        res = analyze_instance(inst_rows, args.k)
        if instance_id in steal:
            res["steal_jiffies"] = steal[instance_id]
        per_instance[instance_id] = res
        print(f"=== {instance_id} ===")
        print(json.dumps(res, indent=2))

    aggregate = {
        "n_instances": len(per_instance),
        "n_activations_total": sum(r["n_activations"] for r in per_instance.values()),
        "miss_rate_pct_mean": float(np.mean([r["miss_rate_pct"] for r in per_instance.values()])) if per_instance else float("nan"),
        "max_consecutive_misses_worst": max((r["max_consecutive_misses"] for r in per_instance.values()), default=0),
    }
    print("=== aggregate ===")
    print(json.dumps(aggregate, indent=2))

    with open(args.output, "w") as f:
        json.dump({"per_instance": per_instance, "aggregate": aggregate}, f, indent=2)


if __name__ == "__main__":
    main()
