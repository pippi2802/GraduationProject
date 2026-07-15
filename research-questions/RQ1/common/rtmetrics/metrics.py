#!/usr/bin/env python3
"""
rtmetrics.metrics — shared metric computations for the RQ1 deterministic-probe
models (model1_1 / model2 / model3 / model4; model1 is independent).

All four models produce the SAME per-job CSV schema (see common/kernel) and
analyse the SAME metrics, so the reductions live here once:

  pct()                 percentile of a sorted list (linear interpolation)
  job_stats()           R/C/delay/dispatch/mid-preempt percentiles + miss/tardiness
  reservation_supply()  alpha_eff (from delivered CPU time) + Delta_eff, for one or
                        MANY per-job CSVs sharing a reservation (used by 2/3/4)
  supply_from_server()  alpha_eff from the sampler's cgroup cpu.stat stream +
                        Delta_eff from dispatch latency (used by model1_1)
"""
from __future__ import annotations

import bisect
import csv
import functools
import json
import os
from array import array
from pathlib import Path


def _is_sorted(seq):
    prev = None
    for v in seq:
        if prev is not None and v < prev:
            return False
        prev = v
    return True


# --------------------------------------------------------------------------- #
def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    if q <= 0:
        return sorted_vals[0]
    if q >= 100:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * q / 100.0
    lo = int(k); hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


# --------------------------------------------------------------------------- #
def job_stats(csv_path):
    """Per-job R/C/delay percentiles + deadline-miss rate + tardiness for one CSV."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return None
    R, C, delay, disp, midpre, tard = [], [], [], [], [], []
    miss = 0; n = 0
    with open(csv_path) as fh:
        header = None
        for r in csv.reader(fh):
            if not r or r[0].startswith("#"):
                continue
            if header is None:
                header = r; idx = {x: i for i, x in enumerate(header)}; continue
            try:
                R.append(float(r[idx["R_wall_us"]]))
                C.append(float(r[idx["C_cputime_us"]]))
                delay.append(float(r[idx["delay_us"]]))
                disp.append(float(r[idx["dispatch_latency_us"]]))
                midpre.append(float(r[idx["mid_job_preempt_us"]]))
                if int(r[idx["deadline_miss"]]):
                    miss += 1
                tard.append(float(r[idx["tardiness_us"]]))
                n += 1
            except (ValueError, KeyError):
                continue
    if n == 0:
        return None
    Rs, Cs = sorted(R), sorted(C)
    return {
        "n": n, "miss": miss, "miss_rate": miss / n,
        "R_p50": pct(Rs, 50), "R_p99": pct(Rs, 99), "R_p999": pct(Rs, 99.9), "R_max": Rs[-1],
        "C_p50": pct(Cs, 50), "C_p99": pct(Cs, 99), "C_max": Cs[-1],
        "delay_p50": pct(sorted(delay), 50), "delay_p99": pct(sorted(delay), 99),
        "dispatch_p99": pct(sorted(disp), 99), "dispatch_max": max(disp),
        "midpreempt_p99": pct(sorted(midpre), 99), "midpreempt_max": max(midpre),
        "tardiness_max": max(tard) if tard else 0.0,
    }


# --------------------------------------------------------------------------- #
def _read_supply_cols(csv_path):
    C, rel, fin, disp = [], [], [], []
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return C, rel, fin, disp
    with open(csv_path) as fh:
        header = None
        for r in csv.reader(fh):
            if not r or r[0].startswith("#"):
                continue
            if header is None:
                header = r; idx = {n: i for i, n in enumerate(header)}; continue
            try:
                C.append(float(r[idx["C_cputime_us"]]))
                rel.append(float(r[idx["release_us"]]))
                fin.append(float(r[idx["finish_us"]]))
                disp.append(float(r[idx["dispatch_latency_us"]]))
            except (ValueError, KeyError):
                continue
    return C, rel, fin, disp


def reservation_supply(csv_paths, Q_us, P_us):
    """(alpha_eff, Delta_eff) for a reservation spanning one or more task CSVs.

    alpha_eff = sum(C_cputime_us) / (last_finish - first_release) -- the bandwidth
    actually DELIVERED; Delta_eff = max dispatch_latency_us. Compare to alpha = Q/P
    and Delta = 2(P-Q). For a container holding MULTIPLE tasks (e.g. model2 intra)
    pass ALL task CSVs; for a single reservation pass one.
    """
    alpha = Q_us / P_us if P_us else None
    delta_theory = 2 * (P_us - Q_us)
    C_total = 0.0; rel_min = None; fin_max = None; disp_max = 0.0; n = 0
    for p in ([csv_paths] if isinstance(csv_paths, (str, Path)) else csv_paths):
        C, rel, fin, disp = _read_supply_cols(p)
        if not C:
            continue
        C_total += sum(C); n += len(C)
        rmin = min(rel); fmax = max(fin)
        rel_min = rmin if rel_min is None else min(rel_min, rmin)
        fin_max = fmax if fin_max is None else max(fin_max, fmax)
        disp_max = max(disp_max, max(disp))
    alpha_eff = None
    if rel_min is not None and fin_max is not None and fin_max > rel_min:
        alpha_eff = C_total / (fin_max - rel_min)
    return {
        "n": n,
        "alpha_theory": round(alpha, 4) if alpha is not None else None,
        "alpha_eff": round(alpha_eff, 4) if alpha_eff is not None else None,
        "delta_theory_us": round(delta_theory, 1),
        "delta_eff_us": round(disp_max, 1),
        "alpha_violation": (alpha_eff is not None and alpha is not None
                            and alpha_eff < 0.98 * alpha),
        "delta_violation": (disp_max > delta_theory),
    }


# --------------------------------------------------------------------------- #
def _load_server_stream(samples_dir):
    p = Path(samples_dir) / "server.csv"
    try:
        mtime = os.path.getmtime(p)
    except OSError:
        mtime = 0.0
    return _load_server_stream_impl(str(Path(samples_dir)), mtime)


@functools.lru_cache(maxsize=64)
def _load_server_stream_impl(samples_dir, _mtime):
    p = Path(samples_dir) / "server.csv"
    if not p.exists():
        return [], []
    mono = array("q"); usage = array("q")
    with open(p) as fh:
        reader = csv.reader(fh)
        mi = ui = None
        for r in reader:
            if not r or r[0].startswith("#"):
                continue
            if mi is None:
                idx = {n: i for i, n in enumerate(r)}
                try:
                    mi = idx["mono_ns"]; ui = idx["usage_usec"]
                except KeyError:
                    return [], []
                continue
            try:
                mono.append(int(r[mi])); usage.append(int(r[ui]))
            except (ValueError, IndexError):
                pass
    if _is_sorted(mono):
        return mono, usage
    order = sorted(range(len(mono)), key=mono.__getitem__)
    return array("q", (mono[i] for i in order)), array("q", (usage[i] for i in order))


def supply_from_server(cell_dir, samples_dir):
    """alpha_eff from the sampler cgroup cpu.stat usage delta over the cell window;
    Delta_eff from the max per-job dispatch_latency in jobs.csv. Used by model1_1
    (one reservation, one jobs.csv). Reads P,Q from the cell's cell.json.
    """
    cell_dir = Path(cell_dir)
    meta = json.loads((cell_dir / "cell.json").read_text())
    P, Q = meta["P_us"], meta["Q_us"]
    alpha = Q / P
    delta_theory = 2 * (P - Q)
    jp = cell_dir / "jobs.csv"
    disp_max = 0.0; t0 = t1 = None
    if jp.exists():
        with open(jp) as fh:
            header = None
            for r in csv.reader(fh):
                if not r or r[0].startswith("#"):
                    continue
                if header is None:
                    header = r; idx = {n: i for i, n in enumerate(header)}; continue
                try:
                    rel = float(r[idx["release_us"]]); fin = float(r[idx["finish_us"]])
                    disp_max = max(disp_max, float(r[idx["dispatch_latency_us"]]))
                except (ValueError, KeyError):
                    continue
                if t0 is None:
                    t0 = rel
                t1 = fin
    mono, usage = _load_server_stream(samples_dir)
    alpha_eff = None
    if mono and t0 is not None and t1 is not None and t1 > t0:
        a = bisect.bisect_right(mono, int(t0 * 1000)) - 1
        b = bisect.bisect_left(mono, int(t1 * 1000))
        a = max(0, a); b = min(len(mono) - 1, b)
        if b > a:
            used_us = usage[b] - usage[a]
            wall_us = (mono[b] - mono[a]) / 1000.0
            if wall_us > 0:
                alpha_eff = used_us / wall_us
    return {
        "alpha_theory": round(alpha, 4),
        "alpha_eff": round(alpha_eff, 4) if alpha_eff is not None else None,
        "delta_theory_us": delta_theory,
        "delta_eff_us": round(disp_max, 1),
        "alpha_violation": (alpha_eff is not None and alpha_eff < 0.98 * alpha),
        "delta_violation": (disp_max > delta_theory),
    }
