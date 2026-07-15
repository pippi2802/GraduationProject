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
import functools
import json
import os
from array import array
from pathlib import Path


def _mtime_of(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _is_sorted(seq):
    prev = None
    for v in seq:
        if prev is not None and v < prev:
            return False
        prev = v
    return True


def _sort_by_mono(mono, series):
    """Return (mono, series) ordered by mono. No-op copy when already ascending
    (the sampler appends in time order), which avoids the memory spike of building
    an index list + reordered copies for a large stream."""
    if _is_sorted(mono):
        return mono, series
    order = sorted(range(len(mono)), key=mono.__getitem__)
    mono2 = array("q", (mono[i] for i in order))
    series2 = {k: array("q", (v[i] for i in order)) for k, v in series.items()}
    return mono2, series2


def _read_clk_tck(path):
    """First comment line of a sampler stream may carry CLK_TCK=<n>."""
    try:
        with open(path) as fh:
            for line in fh:
                if not line.startswith("#"):
                    break
                if "CLK_TCK=" in line:
                    try:
                        return int(line.split("CLK_TCK=")[1].split(",")[0].strip())
                    except ValueError:
                        return 100
    except OSError:
        pass
    return 100


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
    """sorted (mono_ns[], {steal,irq,softirq,freq: values[]}, clk_tck) for a cpu.

    Result is cached per (samples_dir, cpu, cpu.csv mtime) so analyze.py can join
    many cells in one process without re-parsing the (potentially large) stream.
    The file is streamed row-by-row straight into compact int64 arrays (only the
    target cpu is retained), so peak memory stays bounded even for huge streams.
    """
    sd = str(Path(samples_dir))
    return _cpu_series_impl(sd, cpu, _mtime_of(Path(sd) / "cpu.csv"))


@functools.lru_cache(maxsize=64)
def _cpu_series_impl(samples_dir, cpu, _mtime):
    path = Path(samples_dir) / "cpu.csv"
    clk_tck = _read_clk_tck(path)
    mono = array("q"); steal = array("q"); irq = array("q")
    softirq = array("q"); freq = array("q")
    if not path.exists():
        return [], {}, clk_tck
    with open(path) as fh:
        reader = csv.reader(fh)
        ci = mi = si = ii = fi = qi = None
        for r in reader:
            if not r or r[0].startswith("#"):
                continue
            if ci is None:
                idx = {name: i for i, name in enumerate(r)}
                try:
                    ci = idx["cpu"]; mi = idx["mono_ns"]; si = idx["steal"]
                    ii = idx["irq"]; fi = idx["softirq"]; qi = idx["freq_khz"]
                except KeyError:
                    return [], {}, clk_tck
                continue
            try:
                if int(r[ci]) != cpu:
                    continue
                mono.append(int(r[mi])); steal.append(int(r[si])); irq.append(int(r[ii]))
                softirq.append(int(r[fi])); freq.append(int(r[qi]))
            except (ValueError, IndexError):
                continue
    series = {"steal": steal, "irq": irq, "softirq": softirq, "freq": freq}
    mono, series = _sort_by_mono(mono, series)
    return mono, series, clk_tck


def server_series(samples_dir):
    sd = str(Path(samples_dir))
    return _server_series_impl(sd, _mtime_of(Path(sd) / "server.csv"))


@functools.lru_cache(maxsize=64)
def _server_series_impl(samples_dir, _mtime):
    path = Path(samples_dir) / "server.csv"
    mono = array("q"); usage = array("q"); throttled = array("q")
    if not path.exists():
        return [], {}
    with open(path) as fh:
        reader = csv.reader(fh)
        mi = ui = ti = None
        for r in reader:
            if not r or r[0].startswith("#"):
                continue
            if mi is None:
                idx = {name: i for i, name in enumerate(r)}
                try:
                    mi = idx["mono_ns"]; ui = idx["usage_usec"]; ti = idx["throttled_usec"]
                except KeyError:
                    return [], {}
                continue
            try:
                mono.append(int(r[mi])); usage.append(int(r[ui])); throttled.append(int(r[ti]))
            except (ValueError, IndexError):
                continue
    mono, series = _sort_by_mono(mono, {"usage": usage, "throttled": throttled})
    return mono, series


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
        if header is not None and len(data) < len(header):
            continue  # truncated final row (run cut short) -> don't emit a malformed join
        try:
            t0 = int(float(data[jidx["release_us"]]) * 1000)
            t1 = int(float(data[jidx["finish_us"]]) * 1000)
        except (ValueError, KeyError, IndexError):
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
        if header is not None and len(data) < len(header):
            continue  # truncated final row (run cut short) -> don't emit a malformed join
        try:
            t0 = int(float(data[jidx["release_us"]]) * 1000)
            t1 = int(float(data[jidx["finish_us"]]) * 1000)
        except (ValueError, KeyError, IndexError):
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
