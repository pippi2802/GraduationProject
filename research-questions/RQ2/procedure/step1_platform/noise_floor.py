#!/usr/bin/env python3
"""P3, the noise floor: a periodic loop with an EMPTY job, to measure the cost of the runtime itself (timestamps, wake-up) at the
period of your task. Standard library only; run it on the VM, on an RT core, as root for SCHED_FIFO.

    sudo python3 noise_floor.py --period-ms 41.667 --cpu 1 --jobs 20000 --output results/noise_floor/instance0.csv

Same CSV columns as the task runners: cpu_ns is the CPU time of the empty job (the runtime overhead), wait_ns the dispatch
latency (start - release)."""
import argparse, csv, ctypes, ctypes.util, gc, json, os, sys, time

libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


class timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


def now_ns():
    ts = timespec()
    libc.clock_gettime(1, ctypes.byref(ts))                      # CLOCK_MONOTONIC
    return ts.tv_sec * 10**9 + ts.tv_nsec


def sleep_until(t_ns):
    ts = timespec(t_ns // 10**9, t_ns % 10**9)
    while libc.clock_nanosleep(1, 1, ctypes.byref(ts), None) == 4:   # absolute sleep, retried on EINTR
        pass


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--period-ms", type=float, required=True, help="the period of your task")
ap.add_argument("--jobs", type=int, default=20000)
ap.add_argument("--cpu", type=int, default=None)
ap.add_argument("--fifo-prio", type=int, default=50)
ap.add_argument("--output", default="results/noise_floor/instance0.csv")
a = ap.parse_args()

fifo_ok = affinity_ok = False
try:
    if a.cpu is not None:
        os.sched_setaffinity(0, {a.cpu}); affinity_ok = True
    os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(a.fifo_prio)); fifo_ok = True
except OSError as e:
    print(f"warning: affinity / SCHED_FIFO not set ({e}); run as root on an RT core", file=sys.stderr)

period = round(a.period_ms * 1e6)
rows, t0 = [], now_ns() + 10**9
gc.collect(); gc.disable()
for k in range(a.jobs):
    rel = t0 + k * period
    sleep_until(rel)
    s, c = now_ns(), time.thread_time_ns()
    cpu_ns = time.thread_time_ns() - c                           # the empty job: nothing between the two readings
    e = now_ns()
    rows.append(["instance0", k, 0, rel, s, e, cpu_ns, e - rel, s - rel, e - rel - period, int(e <= rel + period), 0, 0])
os.makedirs(os.path.dirname(a.output) or ".", exist_ok=True)
with open(a.output, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["instance_id", "job_id", "frame_idx", "release_ns", "start_ns", "end_ns", "cpu_ns", "response_ns", "wait_ns", "lateness_ns",
                "deadline_met", "skipped", "warmup"])
    w.writerows(rows)
json.dump({"args": vars(a), "sched_fifo_ok": fifo_ok, "affinity_ok": affinity_ok, "start_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
          open(os.path.splitext(a.output)[0] + ".meta.json", "w"), indent=2)
print(f"{a.jobs} jobs of an empty job at {a.period_ms} ms -> {a.output} (fifo {fifo_ok}, affinity {affinity_ok})")
