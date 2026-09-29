#!/usr/bin/env python3
"""Periodic real-time "video frame processor" for KubeDeadline experiments.

Runs under SCHED_FIFO, releases jobs on an absolute CLOCK_MONOTONIC schedule,
logs per-activation timing. Reservation is external (KubeDeadline CBS); this
process only asks for FIFO priority + CPU affinity, never SCHED_DEADLINE.
"""
import argparse, ctypes, ctypes.util, csv, gc, json, os, platform, socket, sys, time

# Must be set before numpy/cv2 import: a BLAS/OpenMP thread pool would
# contend with FIFO pinning and add unpredictable jitter.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import cv2  # noqa: E402
cv2.setNumThreads(1)

CLOCK_MONOTONIC, TIMER_ABSTIME, EINTR = 1, 1, 4
libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


class _timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


def monotonic_ns():
    ts = _timespec()
    libc.clock_gettime(CLOCK_MONOTONIC, ctypes.byref(ts))
    return ts.tv_sec * 1_000_000_000 + ts.tv_nsec


def clock_nanosleep_abs(deadline_ns):
    """Sleep to an absolute CLOCK_MONOTONIC time via libc directly: avoids
    the drift of relative/time.sleep-based scheduling over many periods."""
    ts = _timespec(deadline_ns // 1_000_000_000, deadline_ns % 1_000_000_000)
    while True:
        ret = libc.clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, ctypes.byref(ts), None)
        if ret == 0:
            return
        if ret != EINTR:
            raise OSError(ret, os.strerror(ret))


def make_synthetic_frames(n, width, height, seed=0):
    """Moving shapes + noise so edge/contour density varies between frames."""
    rng = np.random.default_rng(seed)
    frames = []
    for k in range(n):
        img = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.circle(img, (int(k * 7 % width), int(k * 5 % height)), max(5, width // 20), (200, 200, 200), -1)
        rx, ry = int(k * 11 % width), int(k * 3 % height)
        cv2.rectangle(img, (rx, ry), (min(width - 1, rx + width // 10), min(height - 1, ry + height // 10)), (150, 150, 150), -1)
        img = cv2.add(img, rng.integers(0, 40, size=(height, width, 3), dtype=np.uint16).astype(np.uint8))
        frames.append(img)
    return frames


def load_frames(args):
    if not args.input:
        return make_synthetic_frames(args.frames, args.width, args.height)
    cap = cv2.VideoCapture(args.input)
    frames = []
    while len(frames) < args.frames:
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
            if not ok:
                break
        frames.append(cv2.resize(frame, (args.width, args.height)))
    cap.release()
    if not frames:
        raise RuntimeError(f"could not read any frames from {args.input}")
    while len(frames) < args.frames:
        frames.append(frames[len(frames) % len(frames)])
    return frames


class Buffers:
    """Preallocated scratch buffers reused every job: no per-activation
    allocation, which is a source of timing variance."""

    def __init__(self, width, height):
        self.gray = np.empty((height, width), dtype=np.uint8)
        self.blur = np.empty((height, width), dtype=np.uint8)
        self.edges = np.empty((height, width), dtype=np.uint8)
        self.dilated = np.empty((height, width), dtype=np.uint8)
        self.kernel = np.ones((3, 3), np.uint8)


def run_job_body(frame, buf, work, empty_job):
    if empty_job:
        return
    for _ in range(work):
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY, dst=buf.gray)
        cv2.GaussianBlur(buf.gray, (5, 5), 0, dst=buf.blur)
        cv2.Canny(buf.blur, 50, 150, edges=buf.edges)
        cv2.dilate(buf.edges, buf.kernel, dst=buf.dilated)


def set_realtime(args):
    """Best-effort SCHED_FIFO + affinity; must stay runnable without
    privileges (e.g. on a laptop), so failures only warn."""
    fifo_ok = affinity_ok = False
    if args.cpu is not None:
        try:
            os.sched_setaffinity(0, {args.cpu})
            affinity_ok = True
        except OSError as e:
            print(f"warning: sched_setaffinity failed: {e}", file=sys.stderr)
    if args.fifo_prio is not None:
        try:
            os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(args.fifo_prio))
            fifo_ok = True
        except OSError as e:
            print(f"warning: sched_setscheduler(SCHED_FIFO) failed: {e}", file=sys.stderr)
    return fifo_ok, affinity_ok


def proc_stat_cpu():
    try:
        with open("/proc/stat") as f:
            return next(l.strip() for l in f if l.startswith("cpu "))
    except (OSError, StopIteration):
        return None


def build_arg_parser():
    p = argparse.ArgumentParser(description="Periodic real-time video-frame-processor workload")
    p.add_argument("--frames", type=int, default=30)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--input", type=str, default=None)
    p.add_argument("--work", type=int, default=1, help="repetitions of the filter pipeline per job")
    p.add_argument("--empty-job", action="store_true", help="no-op job body; measures runtime overhead/jitter")
    p.add_argument("--period-ms", type=float, default=33.3)
    p.add_argument("--deadline-ms", type=float, default=None, help="default: period")
    p.add_argument("--overrun", choices=["skip", "continue"], default="skip")
    p.add_argument("--jobs", type=int, default=None)
    p.add_argument("--duration-s", type=float, default=None)
    p.add_argument("--start-at", type=int, default=None, help="absolute CLOCK_MONOTONIC ns t0")
    p.add_argument("--offset-ms", type=float, default=0.0)
    p.add_argument("--warmup-jobs", type=int, default=5)
    p.add_argument("--cpu", type=int, default=None)
    p.add_argument("--fifo-prio", type=int, default=None)
    p.add_argument("--instance-id", type=str, default="instance0")
    p.add_argument("--output", type=str, required=True, help="output CSV path; metadata JSON written alongside")
    p.add_argument("--calibrate", action="store_true")
    p.add_argument("--calib-jobs", type=int, default=200)
    p.add_argument("--target-cpu-ms", type=float, default=None)
    return p


def calibrate(args, frames, buf):
    def measure(work):
        samples = np.empty(args.calib_jobs, dtype=np.float64)
        for k in range(args.calib_jobs):
            t0 = time.thread_time_ns()
            run_job_body(frames[k % len(frames)], buf, work, args.empty_job)
            samples[k] = time.thread_time_ns() - t0
        return samples

    if args.target_cpu_ms is None:
        samples, work = measure(args.work), args.work
    else:
        target_ns = args.target_cpu_ms * 1e6
        lo, hi = 1, 1
        while np.median(measure(hi)) < target_ns and hi < 1_000_000:
            hi *= 2
        lo = max(1, hi // 2)
        while lo < hi:
            mid = (lo + hi) // 2
            lo, hi = (mid + 1, hi) if np.median(measure(mid)) < target_ns else (lo, mid)
        work = max(1, lo)
        samples = measure(work)
        print(f"work={work} chosen for target_cpu_ms={args.target_cpu_ms}")

    median = float(np.median(samples))
    cv = float(np.std(samples) / median) if median > 0 else float("nan")
    print(f"cpu_ns: median={median:.0f} p99={np.percentile(samples, 99):.0f} "
          f"max={np.max(samples):.0f} cv={cv:.4f} (n={len(samples)}, work={work})")


def write_csv(path, n, cols, deadline_ns):
    (instance_id, job_id, frame_idx, release_ns, start_ns, end_ns,
     cpu_ns, deadline_met, skipped, warmup) = cols
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["instance_id", "job_id", "frame_idx", "release_ns", "start_ns", "end_ns",
                    "cpu_ns", "response_ns", "wait_ns", "lateness_ns",
                    "deadline_met", "skipped", "warmup"])
        for i in range(n):
            if skipped[i]:
                w.writerow([instance_id[i], job_id[i], frame_idx[i], release_ns[i],
                            "", "", "", "", "", "", 0, 1, warmup[i]])
            else:
                w.writerow([instance_id[i], job_id[i], frame_idx[i], release_ns[i], start_ns[i], end_ns[i],
                            cpu_ns[i], end_ns[i] - release_ns[i], start_ns[i] - release_ns[i],
                            end_ns[i] - (release_ns[i] + deadline_ns),
                            int(deadline_met[i]), int(skipped[i]), int(warmup[i])])


def write_metadata(args, mlock_ok, fifo_ok, affinity_ok, stat_start, stat_end):
    model = threads = None
    try:
        with open("/proc/cpuinfo") as f:
            model = next((l.split(":", 1)[1].strip() for l in f if l.lower().startswith("model name")), None)
    except OSError:
        pass
    try:
        import subprocess
        out = subprocess.run(["lscpu"], capture_output=True, text=True, timeout=5).stdout
        threads = next((l.split(":", 1)[1].strip() for l in out.splitlines() if l.startswith("Thread(s) per core")), None)
    except Exception:
        pass
    meta = {
        "args": vars(args), "instance_id": args.instance_id,
        "start_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hostname": socket.gethostname(), "kernel_version": platform.release(),
        "cpu_model": model, "threads_per_core": threads, "cpu_count": os.cpu_count(),
        "proc_stat_cpu_start": stat_start, "proc_stat_cpu_end": stat_end,
        "mlockall_ok": mlock_ok, "sched_fifo_ok": fifo_ok, "affinity_ok": affinity_ok,
        "python_version": sys.version, "opencv_version": cv2.__version__, "numpy_version": np.__version__,
    }
    with open(os.path.splitext(args.output)[0] + ".meta.json", "w") as f:
        json.dump(meta, f, indent=2)


def main():
    args = build_arg_parser().parse_args()
    if args.deadline_ms is None:
        args.deadline_ms = args.period_ms
    if args.jobs is None and args.duration_s is None and not args.calibrate:
        args.jobs = 1000

    stat_start = proc_stat_cpu()
    frames = load_frames(args)
    buf = Buffers(args.width, args.height)

    mlock_ok = libc.mlockall(1 | 2) == 0  # MCL_CURRENT|MCL_FUTURE
    if not mlock_ok:
        print("warning: mlockall failed (need CAP_IPC_LOCK / privileges)", file=sys.stderr)
    fifo_ok, affinity_ok = set_realtime(args)

    if args.calibrate:
        calibrate(args, frames, buf)
        return

    period_ns = round(args.period_ms * 1_000_000)
    deadline_ns = round(args.deadline_ms * 1_000_000)
    n_frames = len(frames)

    for k in range(args.warmup_jobs):
        run_job_body(frames[k % n_frames], buf, args.work, args.empty_job)

    n_jobs = args.jobs if args.jobs is not None else int(args.duration_s * 1000 / args.period_ms) + 1
    instance_id = np.full(n_jobs, args.instance_id, dtype=object)
    job_id = np.arange(n_jobs, dtype=np.int64)
    frame_idx = job_id % n_frames
    release_ns = np.empty(n_jobs, dtype=np.int64)
    start_ns = np.full(n_jobs, -1, dtype=np.int64)
    end_ns = np.full(n_jobs, -1, dtype=np.int64)
    cpu_ns = np.full(n_jobs, -1, dtype=np.int64)
    deadline_met = np.zeros(n_jobs, dtype=np.int8)
    skipped = np.zeros(n_jobs, dtype=np.int8)
    warmup = np.zeros(n_jobs, dtype=np.int8)

    gc.collect(); gc.freeze(); gc.disable()

    t0 = args.start_at if args.start_at is not None else monotonic_ns() + 1_000_000_000
    offset_ns = round(args.offset_ms * 1_000_000)

    next_k = 0  # next activation to actually run, for overrun=skip
    for jid in range(n_jobs):
        rel = t0 + offset_ns + jid * period_ns
        release_ns[jid] = rel
        if args.overrun == "skip" and jid < next_k:
            skipped[jid] = 1
            continue

        clock_nanosleep_abs(rel)
        s = monotonic_ns()
        c0 = time.thread_time_ns()
        run_job_body(frames[jid % n_frames], buf, args.work, args.empty_job)
        cpu_ns[jid] = time.thread_time_ns() - c0
        e = monotonic_ns()
        start_ns[jid], end_ns[jid] = s, e
        deadline_met[jid] = 1 if e <= rel + deadline_ns else 0

        if args.overrun == "skip":
            k = jid + 1
            while k < n_jobs and (t0 + offset_ns + k * period_ns) < e:
                k += 1
            next_k = max(next_k, k)

    gc.enable()

    cols = (instance_id, job_id, frame_idx, release_ns, start_ns, end_ns,
            cpu_ns, deadline_met, skipped, warmup)
    write_csv(args.output, n_jobs, cols, deadline_ns)
    write_metadata(args, mlock_ok, fifo_ok, affinity_ok, stat_start, proc_stat_cpu())


if __name__ == "__main__":
    main()
