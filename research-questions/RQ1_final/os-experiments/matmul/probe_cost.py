#!/usr/bin/env python3
"""probe_cost.py [--rt-cpu 2] [--sizes 32,64,128,256]   -- cost of ONE multiplication per matrix size on this VM (full-isolation node, agent/pinning as for the runs).
Runs in the calibration pod of mm-full-model1 (node must be labelled for it). Use it to choose MM_N_TIGHT / MM_N_SOFT: a tight cell needs
n_iter * cost <= 0.7 * 10 ms (U = 0.1 -> target 0.7 ms), a soft cell needs cost well below 0.7 * 10 ms = 7 ms to reach U = 0.1 (else it runs at
a higher effective U). Also prints lscpu cache sizes seen by the VM."""
import argparse, subprocess, yaml
from pathlib import Path
import calibrate as c

ap = argparse.ArgumentParser(); ap.add_argument("--rt-cpu", type=int, default=2); ap.add_argument("--sizes", default="32,64,128,256")
a = ap.parse_args()
wl = "model1"
cfg = yaml.safe_load((Path(__file__).resolve().parent / "workloads" / wl / "config.yaml").read_text())
ns, pod = cfg["namespace"], f"{wl}-calib"
c.ensure_pod(cfg, ns, pod)
print(subprocess.run(["kubectl", "exec", "-n", ns, pod, "--", "bash", "-c", "ls /sys/devices/system/cpu/cpu%d/cache/index*/size | head -0; for i in /sys/devices/system/cpu/cpu%d/cache/index*; do echo L$(cat $i/level) $(cat $i/type) $(cat $i/size); done" % (a.rt_cpu, a.rt_cpu)],
                      capture_output=True, text=True).stdout)
for n in [int(x) for x in a.sizes.split(",")]:
    res = c.measure(1, n, False, a.rt_cpu, ns, pod)
    kib = 3 * n * n * 8 / 1024
    print(f"N={n:4d} ({kib:7.0f} KiB): median C per multiplication = {res[0]:9.0f} us  cv={res[1]:.4f}" if res else f"N={n}: no samples")
subprocess.run(["kubectl", "delete", "pod", "-n", ns, pod, "--ignore-not-found", "--wait=false"])
