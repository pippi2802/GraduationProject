#!/usr/bin/env python3
"""
sampler.py — SHARED covariate + supply sampler (node-side, stdlib only).

Used by model1_1 / model2 / model3 / model4 (model1 is independent). Runs in a
privileged, hostPID DaemonSet so /proc and /sys are the HOST's. Emits CUMULATIVE
counters + a CLOCK_MONOTONIC timestamp each tick, so the offline joiner
(common/rtmetrics/covariates.py) can take the delta over ANY per-job window
[release_us, finish_us]. Three streams under --outdir:

  cpu.csv     : per-CPU /proc/stat counters (jiffies) + cpufreq   -> steal / IRQ / softirq
  tasks.csv   : per matmul thread schedstat run-delay + involuntary ctxt switches
  server.csv  : the RT/canary container cgroup cpu.stat (usage_usec, throttled_usec, ...)

Columns are CUMULATIVE (except constants); take deltas offline. Steal/IRQ/softirq
are in USER_HZ jiffies (multiply by 1e6/HZ for microseconds; HZ recorded in header).
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

CLK_TCK = os.sysconf("SC_CLK_TCK")  # USER_HZ (jiffies/sec), typically 100


def mono_ns() -> int:
    # CLOCK_MONOTONIC (NOT _RAW) so this timeline MATCHES the kernel's per-job
    # release/start/finish stamps (matmul cannot sleep on _RAW). This is the
    # join key. _RAW is emitted separately for freeze detection.
    return time.clock_gettime_ns(time.CLOCK_MONOTONIC)


def monoraw_ns() -> int:
    return time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)


def wall_ns() -> int:
    return time.clock_gettime_ns(time.CLOCK_REALTIME)


def read_proc_stat(proc="/proc"):
    """Return {cpu_id: [user,nice,system,idle,iowait,irq,softirq,steal,...]}."""
    out = {}
    try:
        with open(f"{proc}/stat") as fh:
            for line in fh:
                if not line.startswith("cpu"):
                    if out:
                        break          # past the per-cpu block
                    continue
                if line[3:4].isdigit():  # "cpu0", "cpu1", ... (skip the aggregate "cpu ")
                    parts = line.split()
                    cid = int(parts[0][3:])
                    out[cid] = [int(x) for x in parts[1:]]
    except FileNotFoundError:
        pass
    return out


def read_freq(cpu, proc_sys="/sys"):
    try:
        with open(f"{proc_sys}/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq") as fh:
            return int(fh.read().strip())
    except (FileNotFoundError, ValueError, PermissionError):
        return -1


def find_matmul_threads(proc="/proc"):
    """Yield (tid, pid, comm) for every thread whose comm == 'matmul'."""
    for pid in os.listdir(proc):
        if not pid.isdigit():
            continue
        taskdir = f"{proc}/{pid}/task"
        try:
            tids = os.listdir(taskdir)
        except (FileNotFoundError, PermissionError):
            continue
        for tid in tids:
            try:
                with open(f"{taskdir}/{tid}/comm") as fh:
                    comm = fh.read().strip()
            except (FileNotFoundError, PermissionError):
                continue
            if comm == "matmul":
                yield tid, pid, comm


def read_schedstat(proc, pid, tid):
    """schedstat fields: [cpu_time, run_delay, timeslices]. Return run_delay ns."""
    try:
        with open(f"{proc}/{pid}/task/{tid}/schedstat") as fh:
            f = fh.read().split()
            return int(f[1]) if len(f) >= 2 else -1
    except (FileNotFoundError, PermissionError, ValueError):
        return -1


def read_nivcsw(proc, pid, tid):
    try:
        with open(f"{proc}/{pid}/task/{tid}/status") as fh:
            for line in fh:
                if line.startswith("nonvoluntary_ctxt_switches:"):
                    return int(line.split()[1])
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    return -1


def cgroup_cpu_stat(proc, pid, cgroot="/sys/fs/cgroup"):
    """Read the container cgroup cpu.stat for the process (cgroup v2)."""
    try:
        with open(f"{proc}/{pid}/cgroup") as fh:
            rel = fh.read().strip().split("::")[-1]  # v2: "0::/path"
        path = f"{cgroot}{rel}/cpu.stat"
        stat = {}
        with open(path) as fh:
            for line in fh:
                k, v = line.split()
                stat[k] = int(v)
        return stat
    except (FileNotFoundError, PermissionError, ValueError, IndexError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="Shared RQ1 covariate sampler")
    ap.add_argument("--outdir", default="/host/var/lib/rq1/samples")
    ap.add_argument("--rate-hz", type=float, default=1000.0)
    ap.add_argument("--proc", default="/proc")
    ap.add_argument("--sys", default="/sys")
    ap.add_argument("--cgroup-root", default="/sys/fs/cgroup")
    ap.add_argument("--flush-every", type=int, default=200)
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cpu_f = open(outdir / "cpu.csv", "a", buffering=1)
    task_f = open(outdir / "tasks.csv", "a", buffering=1)
    srv_f = open(outdir / "server.csv", "a", buffering=1)
    if cpu_f.tell() == 0:
        cpu_f.write(f"# CLK_TCK={CLK_TCK}\n")
        cpu_f.write("mono_ns,wall_ns,cpu,user,nice,system,idle,iowait,irq,softirq,steal,freq_khz\n")
    if task_f.tell() == 0:
        task_f.write("mono_ns,wall_ns,tid,pid,run_delay_ns,nivcsw\n")
    if srv_f.tell() == 0:
        srv_f.write("mono_ns,wall_ns,pid,usage_usec,user_usec,system_usec,nr_periods,nr_throttled,throttled_usec\n")

    period = 1.0 / a.rate_hz
    n = 0
    next_t = time.monotonic()
    while True:
        m, w = mono_ns(), wall_ns()
        # --- per-CPU counters + freq ---
        for cid, vals in read_proc_stat(a.proc).items():
            v = vals + [0] * 8
            freq = read_freq(cid, a.sys)
            cpu_f.write(f"{m},{w},{cid},{v[0]},{v[1]},{v[2]},{v[3]},{v[4]},{v[5]},{v[6]},{v[7]},{freq}\n")
        # --- matmul threads: run-delay + involuntary ctxt ---
        srv_seen = set()
        for tid, pid, _ in find_matmul_threads(a.proc):
            rd = read_schedstat(a.proc, pid, tid)
            nv = read_nivcsw(a.proc, pid, tid)
            task_f.write(f"{m},{w},{tid},{pid},{rd},{nv}\n")
            if pid not in srv_seen:
                srv_seen.add(pid)
                st = cgroup_cpu_stat(a.proc, pid, a.cgroup_root)
                if st:
                    srv_f.write(f"{m},{w},{pid},{st.get('usage_usec',-1)},"
                                f"{st.get('user_usec',-1)},{st.get('system_usec',-1)},"
                                f"{st.get('nr_periods',-1)},{st.get('nr_throttled',-1)},"
                                f"{st.get('throttled_usec',-1)}\n")
        n += 1
        if n % a.flush_every == 0:
            cpu_f.flush(); task_f.flush(); srv_f.flush()
        next_t += period
        sleep = next_t - time.monotonic()
        if sleep > 0:
            time.sleep(sleep)
        else:
            next_t = time.monotonic()   # fell behind; resync
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
