#!/usr/bin/env python3
"""LiDAR point-cloud preprocessing on the worker, one scan per job (20 Hz, period 50 ms).

    python3 run.py configs/single_core.json [key=value ...]      e.g. jobs=100 period_ms=50

Start-up (not timed): load every scan of the folder (KITTI Velodyne format: float32 x, y, z, reflectance), keep them in RAM.
Then one job per scan, one at a time on one thread: build the point cloud, voxel downsampling, ground-plane removal (RANSAC plane, inliers dropped).
  period_ms = 0: continuous flow, the next scan is handed over the instant the previous one has finished.
  period_ms > 0: one scan released every period (overrun "skip" drops the releases that passed meanwhile).
Several `cpus` = one process per cpu, same start time. Output: <output>_instance<i>.csv (columns as in workload2/run.py,
cpu_ns = thread CPU time of the job) and <output>_instance<i>.meta.json.
"""
import csv, ctypes, ctypes.util, gc, json, multiprocessing, os, platform, socket, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1")                    # one thread: no pool next to the pinned FIFO thread (cpu_ns counts this thread only)

import numpy as np
import open3d as o3d

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


def load_scans(folder, n_scans):
    """all scans of the folder (or the first n_scans): float32 [N, 4] each, as KITTI stores them"""
    files = sorted(f for f in os.listdir(folder) if f.endswith(".bin"))[:n_scans]
    return [np.fromfile(os.path.join(folder, f), dtype=np.float32).reshape(-1, 4) for f in files]


def run_instance(cfg, i, ready, shared_t0):
    inst = f"instance{i}"
    scans = load_scans(cfg["scans"], cfg.get("n_scans"))
    if not scans:
        sys.exit(f"no .bin scans in {cfg['scans']}")
    voxel, dist, iters = cfg.get("voxel_m", 0.2), cfg.get("plane_dist_m", 0.2), cfg.get("plane_iters", 200)
    o3d.utility.random.seed(cfg.get("seed", 0))

    def job(k):
        xyz = np.ascontiguousarray(scans[k % len(scans)][:, :3], dtype=np.float64)    # the scan arrives as a buffer: copy it into the cloud
        pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(xyz))
        down = pcd.voxel_down_sample(voxel)
        _, ground = down.segment_plane(distance_threshold=dist, ransac_n=3, num_iterations=iters)
        down.select_by_index(ground, invert=True)                # what is left once the ground is removed

    cpu, fifo = cfg["cpus"][i], cfg.get("fifo_prio")
    libc.mlockall(3)                                             # best effort: needs IPC_LOCK
    try:
        os.sched_setaffinity(0, {cpu})
        if fifo:
            os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(fifo))
    except OSError as e:
        print(f"warning: affinity/SCHED_FIFO not set ({e})", file=sys.stderr)
    for k in range(cfg.get("warmup", 10)):
        job(k)
    if ready.wait() == 0:                                        # all processes loaded: the last one sets the common start
        shared_t0.value = now_ns() + 2 * 10**9
    ready.wait()
    t0 = shared_t0.value

    n, period = cfg["jobs"], round(cfg.get("period_ms", 0) * 1e6)
    skip = cfg.get("overrun", "skip") == "skip"
    deadline = period or None                                    # continuous mode has no deadline
    rows, prev_end, next_k = [], t0, 0
    gc.collect(); gc.freeze(); gc.disable()
    sleep_until(t0)
    for k in range(n):
        rel = prev_end if period == 0 else t0 + k * period       # continuous: released when the previous one ended
        if period and skip and k < next_k:
            rows.append([inst, k, k % len(scans), rel, "", "", "", "", "", "", 0, 1, 0])
            continue
        if period:
            sleep_until(rel)
        s, c = now_ns(), time.thread_time_ns()
        job(k)
        cpu_ns, e = time.thread_time_ns() - c, now_ns()
        prev_end = e
        rows.append([inst, k, k % len(scans), rel, s, e, cpu_ns, e - rel, s - rel,
                     "" if deadline is None else e - rel - deadline, int(deadline is None or e <= rel + deadline), 0, 0])
        if period and skip:
            while next_k < n and t0 + next_k * period < e:
                next_k += 1
    gc.enable()

    out = f"{cfg['output']}_{inst}"
    with open(out + ".csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["instance_id", "job_id", "frame_idx", "release_ns", "start_ns", "end_ns", "cpu_ns", "response_ns",
                     "wait_ns", "lateness_ns", "deadline_met", "skipped", "warmup"])
        wr.writerows(rows)
    cpu_model = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), None)
    json.dump({"args": {**cfg, "instance_id": inst, "cpu": cpu}, "instance_id": inst, "n_scans": len(scans),
               "start_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "hostname": socket.gethostname(),
               "kernel_version": platform.release(), "cpu_model": cpu_model, "open3d": o3d.__version__},
              open(out + ".meta.json", "w"), indent=2)
    ran = np.array([r[6] for r in rows if r[6] != ""]) / 1e6
    print(f"[{inst}] {len(ran)} jobs run, {n - len(ran)} skipped; cpu_ms median={np.median(ran):.2f} "
          f"p99={np.percentile(ran, 99):.2f} max={ran.max():.2f}", flush=True)


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1]))
    for kv in sys.argv[2:]:                                      # optional overrides: run.py cfg.json jobs=100 n_scans=100
        key, value = kv.split("=", 1)
        cfg[key] = json.loads(value)
    n = len(cfg["cpus"])
    ready, t0 = multiprocessing.Barrier(n), multiprocessing.Value("q", 0)
    procs = [multiprocessing.Process(target=run_instance, args=(cfg, i, ready, t0)) for i in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    sys.exit(any(p.exitcode for p in procs))
