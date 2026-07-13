#!/usr/bin/env python3
"""
rtmetrics.covariates — shared per-job covariate join for the RQ1 models.

The kernel's per-job CSV carries release_us/finish_us on CLOCK_MONOTONIC; the
sampler's streams carry cumulative counters on the SAME clock (mono_ns). For each
job window [release, finish] we delta the RT-core counters and emit the additive
attribution inputs so the thesis can fit  R - C ~= I_steal + I_IRQ + I_preempt + eps.

Two join wrappers (same primitives, different output shape):
  join_model1_1(cell_dir, samples_dir)  -> ONE jobs_with_covariates.csv (single
      reservation; rt_cpu + server usage from cell.json), used by model1_1.
  join_percell(cell_dir, samples_dir)   -> <name>_with_covariates.csv for EVERY
      per-job CSV in the cell (per-task/per-reservation), used by model2/3/4.
"""
from __future__ import annotations

import bisect
import csv
import json
from pathlib import Path


# --------------------------------------------------------------------------- #
# stream loaders
# --------------------------------------------------------------------------- #
def _load_stream(path):
    path = Path(path)
    if not path.exists():
        return [], None, 100
    rows = []; header = None; clk_tck = 100
    with open(path) as fh:
        for r in csv.reader(fh):
            if not r:
                continue
            if r[0].startswith("#"):
                if "CLK_TCK=" in r[0]:
                    try:
                        clk_tck = int(r[0].split("CLK_TCK=")[1])
                    except ValueError:
                        pass
                continue
            if header is None:
                header = r
                continue
            rows.append(r)
    return rows, header, clk_tck


def cpu_series(samples_dir, cpu):
    """sorted (mono_ns[], {steal,irq,softirq,freq: values[]}, clk_tck) for a cpu."""
    rows, header, clk_tck = _load_stream(Path(samples_dir) / "cpu.csv")
    if not rows or header is None:
        return [], {}, clk_tck
    idx = {name: i for i, name in enumerate(header)}
    mono, steal, irq, softirq, freq = [], [], [], [], []
    for r in rows:
        try:
            if int(r[idx["cpu"]]) != cpu:
                continue
            mono.append(int(r[idx["mono_ns"]]))
            steal.append(int(r[idx["steal"]]))
            irq.append(int(r[idx["irq"]]))
            softirq.append(int(r[idx["softirq"]]))
            freq.append(int(r[idx["freq_khz"]]))
        except (ValueError, KeyError):
            continue
    order = sorted(range(len(mono)), key=lambda i: mono[i])
    mono = [mono[i] for i in order]
    return mono, {"steal": [steal[i] for i in order], "irq": [irq[i] for i in order],
                  "softirq": [softirq[i] for i in order], "freq": [freq[i] for i in order]}, clk_tck


def server_series(samples_dir):
    rows, header, _ = _load_stream(Path(samples_dir) / "server.csv")
    if not rows or header is None:
        return [], {}
    idx = {name: i for i, name in enumerate(header)}
    mono, usage, throttled = [], [], []
    for r in rows:
        try:
            mono.append(int(r[idx["mono_ns"]]))
            usage.append(int(r[idx["usage_usec"]]))
            throttled.append(int(r[idx["throttled_usec"]]))
        except (ValueError, KeyError):
            continue
    order = sorted(range(len(mono)), key=lambda i: mono[i])
    return [mono[i] for i in order], {"usage": [usage[i] for i in order],
                                      "throttled": [throttled[i] for i in order]}


def delta_over(mono, series, t0, t1):
    """Cumulative-counter delta between the samples bracketing [t0,t1] (ns)."""
    if not mono:
        return None
    i0 = bisect.bisect_right(mono, t0) - 1
    i1 = bisect.bisect_left(mono, t1)
    i0 = max(0, i0); i1 = min(len(mono) - 1, i1)
    if i1 <= i0:
        return 0
    return series[i1] - series[i0]


def mean_over(mono, series, t0, t1):
    if not mono:
        return -1
    i0 = bisect.bisect_left(mono, t0)
    i1 = bisect.bisect_right(mono, t1)
    seg = [v for v in series[i0:i1] if v > 0]
    return sum(seg) / len(seg) if seg else -1


# --------------------------------------------------------------------------- #
# join wrappers
# --------------------------------------------------------------------------- #
def _iter_jobs(jobs_path):
    header = None
    with open(jobs_path) as fh:
        for r in csv.reader(fh):
            if not r or r[0].startswith("#"):
                continue
            if header is None:
                header = r
                yield ("__header__", header, {n: i for i, n in enumerate(header)})
                continue
            yield ("row", r, None)


def join_model1_1(cell_dir, samples_dir):
    """Single-reservation join -> jobs_with_covariates.csv (model1_1 semantics)."""
    cell_dir = Path(cell_dir); samples_dir = Path(samples_dir)
    meta = json.loads((cell_dir / "cell.json").read_text()) if (cell_dir / "cell.json").exists() else {}
    rt = meta.get("rt_cpuset")
    try:
        cpu = int(str(rt).split(",")[0].split("-")[0]) if rt is not None else meta.get("cpu_used", 0)
    except (ValueError, TypeError):
        cpu = 0
    mono_c, cser, clk_tck = cpu_series(samples_dir, cpu)
    mono_s, sser = server_series(samples_dir)
    j2us = 1_000_000.0 / clk_tck
    jobs_p = cell_dir / "jobs.csv"
    if not jobs_p.exists():
        return 0
    out_rows = []; header = None; jidx = None
    for kind, data, extra in _iter_jobs(jobs_p):
        if kind == "__header__":
            header = data; jidx = extra; continue
        try:
            t0 = int(float(data[jidx["release_us"]]) * 1000)
            t1 = int(float(data[jidx["finish_us"]]) * 1000)
        except (ValueError, KeyError):
            continue
        steal = delta_over(mono_c, cser.get("steal", []), t0, t1)
        irq = delta_over(mono_c, cser.get("irq", []), t0, t1)
        softirq = delta_over(mono_c, cser.get("softirq", []), t0, t1)
        freq = mean_over(mono_c, cser.get("freq", []), t0, t1)
        usage = delta_over(mono_s, sser.get("usage", []), t0, t1)
        throt = delta_over(mono_s, sser.get("throttled", []), t0, t1)
        out_rows.append(data + [
            f"{steal * j2us:.1f}" if steal is not None else "",
            f"{irq * j2us:.1f}" if irq is not None else "",
            f"{softirq * j2us:.1f}" if softirq is not None else "",
            f"{usage:.1f}" if usage is not None else "",
            f"{throt:.1f}" if throt is not None else "",
            f"{freq:.0f}",
        ])
    out_header = header + ["steal_us", "irq_us", "softirq_us",
                           "server_usage_us", "throttled_us", "freq_khz_mean"]
    out_p = cell_dir / "jobs_with_covariates.csv"
    with open(out_p, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(out_header); w.writerows(out_rows)
    print(f"[join] {out_p}  ({len(out_rows)} jobs, rt_cpu={cpu})")
    return len(out_rows)


def _file_cpu_map(meta):
    out = {}
    pl = meta.get("placements", {})
    if "tasks" in pl:
        cpu = pl.get("shared_cpu")
        for t in pl["tasks"]:
            out[t["file"]] = t.get("cpu", cpu)
    if "target" in pl:
        tg = pl["target"]
        out[tg["file"]] = tg.get("cpu")
        for nb in pl.get("neighbours", []):
            out[nb["file"]] = nb.get("cpu")
    return out


def _join_one_file(csv_path, cpu, samples_dir):
    mono_c, cser, clk_tck = cpu_series(samples_dir, cpu if cpu is not None else -1)
    j2us = 1_000_000.0 / clk_tck
    out_rows = []; header = None; jidx = None
    for kind, data, extra in _iter_jobs(csv_path):
        if kind == "__header__":
            header = data; jidx = extra; continue
        try:
            t0 = int(float(data[jidx["release_us"]]) * 1000)
            t1 = int(float(data[jidx["finish_us"]]) * 1000)
        except (ValueError, KeyError):
            continue
        steal = delta_over(mono_c, cser.get("steal", []), t0, t1)
        irq = delta_over(mono_c, cser.get("irq", []), t0, t1)
        softirq = delta_over(mono_c, cser.get("softirq", []), t0, t1)
        freq = mean_over(mono_c, cser.get("freq", []), t0, t1)
        out_rows.append(data + [
            f"{steal * j2us:.1f}" if steal is not None else "",
            f"{irq * j2us:.1f}" if irq is not None else "",
            f"{softirq * j2us:.1f}" if softirq is not None else "",
            f"{freq:.0f}",
        ])
    if header is None:
        return 0
    out_header = header + ["steal_us", "irq_us", "softirq_us", "freq_khz_mean"]
    out_p = Path(csv_path).with_name(Path(csv_path).stem + "_with_covariates.csv")
    with open(out_p, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(out_header); w.writerows(out_rows)
    print(f"[join] {out_p}  ({len(out_rows)} jobs, cpu={cpu})")
    return len(out_rows)


def join_percell(cell_dir, samples_dir):
    """Per-file join -> <name>_with_covariates.csv for every per-job CSV in the cell."""
    cell_dir = Path(cell_dir); samples_dir = Path(samples_dir)
    meta = json.loads((cell_dir / "cell.json").read_text()) if (cell_dir / "cell.json").exists() else {}
    cmap = _file_cpu_map(meta)
    n = 0
    for csvp in sorted(cell_dir.glob("*.csv")):
        if csvp.name.endswith("_with_covariates.csv"):
            continue
        n += _join_one_file(csvp, cmap.get(csvp.name), samples_dir)
    if not cmap:
        print(f"[join] WARN no placements in cell.json for {cell_dir}; joined by name only")
    return n
