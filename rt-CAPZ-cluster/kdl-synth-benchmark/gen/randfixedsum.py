#!/usr/bin/env python3
"""Synthetic periodic task-set generator (RandFixedSum).

Generates implicit-deadline periodic task sets following the KubeDeadline
synthetic experiment:

  * number of tasks  n  drawn uniformly from [n_min, n_max]   (default 4..12)
  * total utilisation U swept across [u_min, u_max]           (default 0.6..1.8)
  * per-task utilisations via Roger Stafford's RandFixedSum   (sum == U)
  * periods T_i sampled log-uniformly in [t_min_ms, t_max_ms] (default 10..100 ms)
  * C_i = u_i * T_i  (microseconds),  D_i = T_i

Each set is written as JSON to the output directory with metadata
(n, U, seed) embedded in both the filename and the file body.

The per-task object schema consumed by the C workload is:
    { "id": 0, "c_us": 4200, "t_us": 33000 }

Requires: numpy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np


def rand_fixed_sum(n: int, m: int, u_total: float, rng: np.random.Generator) -> np.ndarray:
    """Roger Stafford's RandFixedSum.

    Return an (m, n) array; each of the m rows has n values in [0, 1] that
    sum exactly to ``u_total``, sampled uniformly from that simplex slice.
    """
    if not (0.0 <= u_total <= n):
        raise ValueError(f"u_total={u_total} out of range [0, {n}]")

    # Rescale so the target sum s lies in [0, n] with the standard algorithm.
    s = float(u_total)
    k = min(int(np.floor(s)), n - 1)
    s = max(min(s, float(k + 1)), float(k))

    s1 = s - np.arange(k, k - n, -1.0)
    s2 = np.arange(k + n, k, -1.0) - s

    w = np.zeros((n, n + 1))
    w[0, 1] = np.finfo(float).max
    t = np.zeros((n - 1, n))

    for i in range(2, n + 1):
        tmp1 = w[i - 2, 1 : i + 1] * s1[0:i] / float(i)
        tmp2 = w[i - 2, 0:i] * s2[n - i : n] / float(i)
        w[i - 1, 1 : i + 1] = tmp1 + tmp2
        tmp3 = w[i - 1, 1 : i + 1] + np.finfo(float).tiny
        tmp4 = np.asarray(s2[n - i : n] > s1[0:i], dtype=float)
        t[i - 2, 0:i] = (tmp2 / tmp3) * tmp4 + (1.0 - tmp1 / tmp3) * (1.0 - tmp4)

    x = np.zeros((n, m))
    rt = rng.random((n - 1, m))   # selection thresholds
    rs = rng.random((n - 1, m))   # value thresholds
    ss = np.full(m, s)
    j = np.full(m, k + 1)
    sm = np.zeros(m)
    pr = np.ones(m)

    for i in range(n - 1, 0, -1):
        e = (rt[n - i - 1, :] <= t[i - 1, j - 1]).astype(float)
        sx = rs[n - i - 1, :] ** (1.0 / i)
        sm = sm + (1.0 - sx) * pr * ss / float(i + 1)
        pr = sx * pr
        x[n - i - 1, :] = sm + pr * e
        ss = ss - e
        j = j - e.astype(int)

    x[n - 1, :] = sm + pr * ss

    # Randomly permute the order within each column to remove ordering bias.
    for col in range(m):
        x[:, col] = rng.permutation(x[:, col])

    return x.T  # shape (m, n)


def make_taskset(n: int, u_total: float, t_min_ms: float, t_max_ms: float,
                 rng: np.random.Generator) -> list[dict]:
    """Build one task set: utilisations via RandFixedSum, log-uniform periods."""
    utils = rand_fixed_sum(n, 1, u_total, rng)[0]

    log_lo, log_hi = np.log(t_min_ms), np.log(t_max_ms)
    periods_ms = np.exp(rng.uniform(log_lo, log_hi, size=n))

    tasks = []
    for i in range(n):
        t_us = int(round(periods_ms[i] * 1000.0))
        c_us = int(round(utils[i] * t_us))
        c_us = max(c_us, 1)
        tasks.append({"id": i, "c_us": c_us, "t_us": t_us})
    return tasks


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="RandFixedSum periodic task-set generator")
    p.add_argument("--out-dir", default=os.path.join(os.path.dirname(__file__), "tasksets"))
    p.add_argument("--count", type=int, default=150, help="number of task sets")
    p.add_argument("--n-min", type=int, default=4)
    p.add_argument("--n-max", type=int, default=12)
    p.add_argument("--u-min", type=float, default=0.6)
    p.add_argument("--u-max", type=float, default=1.8,
                   help="utilisation cap (1.8 for the 2-physical-core node)")
    p.add_argument("--u-step", type=float, default=0.2,
                   help="sweep step for U across [u-min, u-max]")
    p.add_argument("--t-min-ms", type=float, default=10.0)
    p.add_argument("--t-max-ms", type=float, default=100.0)
    p.add_argument("--seed", type=int, default=1234)
    args = p.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    # Build the utilisation sweep grid, then cycle through it.
    n_steps = max(1, int(round((args.u_max - args.u_min) / args.u_step)) + 1)
    u_grid = np.linspace(args.u_min, args.u_max, n_steps)

    written = 0
    for idx in range(args.count):
        u_total = float(u_grid[idx % len(u_grid)])
        n = int(rng.integers(args.n_min, args.n_max + 1))
        set_seed = int(rng.integers(0, 2**31 - 1))
        set_rng = np.random.default_rng(set_seed)
        tasks = make_taskset(n, u_total, args.t_min_ms, args.t_max_ms, set_rng)

        set_id = f"set{idx:03d}"
        doc = {
            "taskset_id": set_id,
            "n": n,
            "util": round(u_total, 4),
            "seed": set_seed,
            "t_min_ms": args.t_min_ms,
            "t_max_ms": args.t_max_ms,
            "tasks": tasks,
            # filled in later by carts_wrapper.py:
            "reservation": None,
        }
        fname = f"{set_id}_n{n}_U{u_total:.2f}.json"
        with open(os.path.join(args.out_dir, fname), "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        written += 1

    print(f"wrote {written} task sets to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
