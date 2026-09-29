#!/usr/bin/env python3
"""Multi-instance launcher: one rt_video.py PROCESS per RT core.

Processes, never threads, because of the GIL - each instance needs its own
FIFO priority and CPU affinity, and Python threads share one interpreter
lock so they cannot run truly in parallel on separate cores anyway.
"""
import argparse
import json
import os
import subprocess
import sys
import time

try:
    import yaml
except ImportError:
    yaml = None

# Common time base so multiple instances' periodic schedules are aligned,
# which matters for reproducing multi-core interference/contention scenarios.
START_AHEAD_S = 3.0
NS_PER_S = 1_000_000_000
RT_VIDEO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rt_video.py")


def load_config(path):
    with open(path) as f:
        if path.endswith((".yml", ".yaml")):
            if yaml is None:
                raise RuntimeError("PyYAML not installed; use a .json config or `pip install pyyaml`")
            return yaml.safe_load(f)
        return json.load(f)


def instance_to_argv(inst):
    argv = [sys.executable, RT_VIDEO_PATH, "--output", inst["output"]]
    argv += ["--instance-id", str(inst["instance_id"])]
    argv += ["--cpu", str(inst["cpu"])]
    if "fifo_prio" in inst:
        argv += ["--fifo-prio", str(inst["fifo_prio"])]
    argv += ["--period-ms", str(inst["period_ms"])]
    if "deadline_ms" in inst:
        argv += ["--deadline-ms", str(inst["deadline_ms"])]
    argv += ["--work", str(inst.get("work", 1))]
    argv += ["--width", str(inst.get("width", 1280))]
    argv += ["--height", str(inst.get("height", 720))]
    argv += ["--frames", str(inst.get("frames", 30))]
    if inst.get("input"):
        argv += ["--input", inst["input"]]
    argv += ["--offset-ms", str(inst.get("offset_ms", 0))]
    if "jobs" in inst:
        argv += ["--jobs", str(inst["jobs"])]
    elif "duration_s" in inst:
        argv += ["--duration-s", str(inst["duration_s"])]
    argv += ["--overrun", inst.get("overrun", "skip")]
    if inst.get("empty_job"):
        argv += ["--empty-job"]
    return argv


def main():
    p = argparse.ArgumentParser(description="Launch one rt_video.py process per instance, time-aligned")
    p.add_argument("config", help="JSON or YAML file listing instances")
    p.add_argument("--start-ahead-s", type=float, default=START_AHEAD_S)
    args = p.parse_args()

    config = load_config(args.config)
    instances = config["instances"] if isinstance(config, dict) else config
    start_at = time.clock_gettime_ns(time.CLOCK_MONOTONIC) + int(args.start_ahead_s * NS_PER_S)

    procs = []
    for inst in instances:
        argv = instance_to_argv(inst) + ["--start-at", str(start_at)]
        print("launching:", " ".join(argv))
        procs.append((inst["instance_id"], subprocess.Popen(argv)))

    exit_codes = {}
    for instance_id, proc in procs:
        exit_codes[instance_id] = proc.wait()

    print("exit codes:", exit_codes)
    if any(code != 0 for code in exit_codes.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
