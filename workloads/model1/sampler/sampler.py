#!/usr/bin/env python3
"""
Model 1 covariate + cgroup sampler (stdlib only; runs as a privileged,
hostPID DaemonSet). Samples the RT-under-test and canary rt-app processes on a
common CLOCK_MONOTONIC_RAW timeline and appends CSV rows continuously.

Because the DaemonSet is long-lived across the whole sweep (like the canary),
it writes ONE continuous stream per node to hostPath; the orchestrator records
each cell's [start,end] wall window and parse/slice_covariates.py cuts per-cell
slices into results/<timeblock>/<scale>/U<U>/.

Discovery (no hardcoded PIDs): scans /proc for processes named 'rt-app', finds
each one's SCHED_FIFO worker thread (via /proc/<tid>/stat policy field), its
last-run CPU, and its cgroup cpu.stat. Labels each as 'rt' or 'canary' using
cpu-map.json (rt_cpu / canary_cpu) when available, else by CPU parity.

Outputs (append):
  <outdir>/server.csv       supply: cgroup cpu.stat per target
  <outdir>/covariates.csv   steal / run-delay / irq / softirq / freeze flag

Env / args:
  --outdir     (default /host/var/lib/model1/samples)
  --map        cpu-map.json from node-prep (default /host/var/lib/model1/cpu-map.json)
  --rate-hz    sampling frequency (default 1000; oversampling soft scale is fine)
  --cgroot     host cgroup2 root (default /host/sys/fs/cgroup)
  --procroot   host proc (default /proc; hostPID makes host PIDs visible)
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

RUNNING = True


def _stop(signum, frame):
    global RUNNING
    RUNNING = False


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

CLK_TCK = os.sysconf("SC_CLK_TCK")


# --------------------------------------------------------------------------- #
# /proc helpers
# --------------------------------------------------------------------------- #
def read_text(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except (OSError, IOError):
        return None


def parse_stat_fields(stat_line: str):
    """Split /proc/<pid>/stat safely around the comm in parens."""
    lpar = stat_line.find("(")
    rpar = stat_line.rfind(")")
    if lpar < 0 or rpar < 0:
        return None
    pid = stat_line[:lpar].strip()
    comm = stat_line[lpar + 1:rpar]
    rest = stat_line[rpar + 1:].split()
    # rest[0] = state (field 3). policy = field 41 -> rest index 41-3 = 38.
    # processor (last CPU) = field 39 -> rest index 36.
    return pid, comm, rest


def find_rtapp_threads(procroot: str):
    """Return list of dicts: {pid, tid, cpu, policy} for FIFO rt-app workers."""
    out = []
    for entry in os.listdir(procroot):
        if not entry.isdigit():
            continue
        pid = entry
        comm = read_text(f"{procroot}/{pid}/comm")
        # rt-app main thread comm is 'rt-app'; worker threads may be named 'rt'
        if comm is None:
            continue
        taskdir = f"{procroot}/{pid}/task"
        try:
            tids = os.listdir(taskdir)
        except OSError:
            continue
        for tid in tids:
            stat = read_text(f"{taskdir}/{tid}/stat")
            if not stat:
                continue
            parsed = parse_stat_fields(stat)
            if not parsed:
                continue
            _, tcomm, rest = parsed
            if len(rest) < 39:
                continue
            try:
                policy = int(rest[38])   # field 41 = policy
                cpu = int(rest[36])      # field 39 = processor (last CPU)
            except (ValueError, IndexError):
                continue
            # SCHED_FIFO = 1. Only sample the RT worker thread(s).
            if policy != 1:
                continue
            # confine to actual rt-app processes
            if comm.strip() != "rt-app" and tcomm != "rt-app" and "rt" not in tcomm:
                continue
            out.append({"pid": pid, "tid": tid, "cpu": cpu})
    return out


def read_schedstat(procroot: str, pid: str, tid: str):
    """/proc/<pid>/task/<tid>/schedstat -> (cpu_time_ns, run_delay_ns, timeslices)."""
    txt = read_text(f"{procroot}/{pid}/task/{tid}/schedstat")
    if not txt:
        return (None, None, None)
    parts = txt.split()
    if len(parts) < 3:
        return (None, None, None)
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return (None, None, None)


def cgroup_cpu_stat(procroot: str, cgroot: str, pid: str):
    """Resolve the task's cgroup and read cpu.stat (cgroup v2)."""
    cg = read_text(f"{procroot}/{pid}/cgroup")
    if not cg:
        return {}
    rel = None
    for line in cg.splitlines():
        # v2 unified line: "0::/kubepods.slice/.../scope"
        if line.startswith("0::"):
            rel = line.split("::", 1)[1]
            break
    if rel is None:
        return {}
    stat = read_text(f"{cgroot}{rel}/cpu.stat")
    if not stat:
        return {}
    d = {}
    for line in stat.splitlines():
        k, _, v = line.partition(" ")
        try:
            d[k] = int(v)
        except ValueError:
            pass
    return d


def proc_stat_cpu(procroot: str, cpu: int):
    """Per-CPU line of /proc/stat -> steal/irq/softirq (jiffies, cumulative)."""
    txt = read_text(f"{procroot}/stat")
    if not txt:
        return {}
    want = f"cpu{cpu}"
    for line in txt.splitlines():
        if line.startswith(want + " ") or line == want:
            f = line.split()
            # cpuN user nice system idle iowait irq softirq steal guest guest_nice
            def g(i):
                return int(f[i]) if len(f) > i else 0
            return {"irq": g(6), "softirq": g(7), "steal": g(8)}
    return {}


def sum_column_for_cpu(procroot: str, fname: str, cpu: int):
    """Sum the per-CPU column across all lines in /proc/interrupts|softirqs."""
    txt = read_text(f"{procroot}/{fname}")
    if not txt:
        return None
    lines = txt.splitlines()
    if not lines:
        return None
    header = lines[0].split()
    # header columns are CPU0 CPU1 ...  find index of our CPU
    target = f"CPU{cpu}"
    try:
        col = header.index(target)
    except ValueError:
        return None
    total = 0
    for line in lines[1:]:
        parts = line.split()
        # parts[0] is the IRQ label ("0:", "NMI", ...). counts start at parts[1].
        idx = col + 1
        if len(parts) > idx and parts[idx].isdigit():
            total += int(parts[idx])
    return total


# --------------------------------------------------------------------------- #
# CSV writers
# --------------------------------------------------------------------------- #
SERVER_HEADER = (
    "ts_raw_ns,ts_wall_ns,target,pid,cpu,"
    "usage_usec,user_usec,system_usec,nr_periods,nr_throttled,throttled_usec\n"
)
COV_HEADER = (
    "ts_raw_ns,ts_wall_ns,target,pid,tid,cpu,"
    "steal_jiffies,irq_jiffies,softirq_jiffies,"
    "sched_runtime_ns,sched_rundelay_ns,sched_timeslices,"
    "interrupts_cum,softirqs_cum,gap_flag\n"
)


def open_append(path: Path, header: str):
    new = not path.exists() or path.stat().st_size == 0
    fh = open(path, "a", encoding="utf-8")
    if new:
        fh.write(header)
        fh.flush()
    return fh


def role_for_cpu(cpu: int, cpumap: dict) -> str:
    if not cpumap:
        return f"cpu{cpu}"
    if cpu == cpumap.get("rt_cpu"):
        return "rt"
    if cpu == cpumap.get("canary_cpu"):
        return "canary"
    return f"cpu{cpu}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="/host/var/lib/model1/samples")
    ap.add_argument("--map", default="/host/var/lib/model1/cpu-map.json")
    ap.add_argument("--rate-hz", type=float, default=1000.0)
    ap.add_argument("--cgroot", default="/host/sys/fs/cgroup")
    ap.add_argument("--procroot", default="/proc")
    ap.add_argument("--rediscover-every", type=int, default=1000,
                    help="re-scan /proc for rt-app procs every N samples")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cpumap = {}
    mp = read_text(args.map)
    if mp:
        try:
            cpumap = json.loads(mp)
        except json.JSONDecodeError:
            pass

    server_fh = open_append(outdir / "server.csv", SERVER_HEADER)
    cov_fh = open_append(outdir / "covariates.csv", COV_HEADER)

    interval = 1.0 / args.rate_hz
    expected_ns = int(interval * 1e9)
    gap_mult = 5  # matches config sampling.covariates.freeze_detection.gap_flag_multiplier
    prev_raw = None
    threads = find_rtapp_threads(args.procroot)
    n = 0

    sys.stderr.write(
        f"[sampler] rate={args.rate_hz}Hz targets={len(threads)} outdir={outdir}\n"
    )
    while RUNNING:
        t0 = time.perf_counter()
        raw = time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
        wall = time.clock_gettime_ns(time.CLOCK_REALTIME)
        gap_flag = 1 if (prev_raw is not None and (raw - prev_raw) > gap_mult * expected_ns) else 0
        prev_raw = raw

        if n % args.rediscover_every == 0:
            threads = find_rtapp_threads(args.procroot)

        for th in threads:
            pid, tid, cpu = th["pid"], th["tid"], th["cpu"]
            role = role_for_cpu(cpu, cpumap)
            cs = cgroup_cpu_stat(args.procroot, args.cgroot, pid)
            server_fh.write(
                f"{raw},{wall},{role},{pid},{cpu},"
                f"{cs.get('usage_usec','')},{cs.get('user_usec','')},"
                f"{cs.get('system_usec','')},{cs.get('nr_periods','')},"
                f"{cs.get('nr_throttled','')},{cs.get('throttled_usec','')}\n"
            )
            ps = proc_stat_cpu(args.procroot, cpu)
            rt_ns, delay_ns, slices = read_schedstat(args.procroot, pid, tid)
            irq_cum = sum_column_for_cpu(args.procroot, "interrupts", cpu)
            sirq_cum = sum_column_for_cpu(args.procroot, "softirqs", cpu)
            cov_fh.write(
                f"{raw},{wall},{role},{pid},{tid},{cpu},"
                f"{ps.get('steal','')},{ps.get('irq','')},{ps.get('softirq','')},"
                f"{rt_ns if rt_ns is not None else ''},"
                f"{delay_ns if delay_ns is not None else ''},"
                f"{slices if slices is not None else ''},"
                f"{irq_cum if irq_cum is not None else ''},"
                f"{sirq_cum if sirq_cum is not None else ''},{gap_flag}\n"
            )

        n += 1
        if n % 256 == 0:
            server_fh.flush()
            cov_fh.flush()

        # pace to the target rate
        dt = time.perf_counter() - t0
        sleep = interval - dt
        if sleep > 0:
            time.sleep(sleep)

    server_fh.flush(); server_fh.close()
    cov_fh.flush(); cov_fh.close()
    sys.stderr.write("[sampler] stopped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
