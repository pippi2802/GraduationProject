#!/usr/bin/env python3
"""Audio stream processor for KubeDeadline experiments: a streaming convolution reverb.

    python3 run.py cpus=[1] period_ms=10 jobs=100000 output=/results/single_core     (every parameter is key=value, see CFG)

Every period one block of 10 ms of audio (480 samples at 48 kHz) arrives and is processed: FFT of the block, partitioned
convolution with a long impulse response (the reverb), inverse FFT, soft limiter. A job = one block. The audio is a
synthetic 30 s stream (noise + tones) generated before the loop; nothing is allocated or generated inside a job.
Several cpus = one process per cpu, same start time. Writes <output>_instance<i>.csv (columns as in workload/rt_video.py,
cpu_ns = thread CPU time of the job) and <output>_instance<i>.meta.json. A release that passed during an overrun is skipped.
"""
import csv, ctypes, ctypes.util, gc, json, multiprocessing, os, platform, socket, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np

CFG = dict(cpus=[1], fifo_prio=50, period_ms=10, jobs=100000, partitions=1000, warmup=200, output="/results/single_core")
FS, B = 48000, 480                                              # sample rate, block = 10 ms
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


def run_instance(cfg, i, ready, shared_t0):
    inst, P = f"instance{i}", cfg["partitions"]
    rng = np.random.default_rng(i)
    t = np.arange(30 * FS) / FS
    stream = (0.3 * np.sin(2 * np.pi * 440 * t) + 0.2 * np.sin(2 * np.pi * 1250 * t) + 0.1 * rng.standard_normal(len(t))).astype(np.float32)
    ir = rng.standard_normal(P * B) * np.exp(-3 * np.arange(P * B) / (P * B))        # reverb tail of P blocks (P * 10 ms)
    H = np.fft.rfft(ir.reshape(P, B), 2 * B, axis=1).astype(np.complex64)             # [P, B+1] spectra of the partitions
    fdl = np.zeros_like(H)                                                           # spectra of the last P input blocks
    prev = np.zeros(B, dtype=np.float32)
    n_blocks = len(stream) // B

    def job(k):
        nonlocal fdl, prev
        block = stream[(k % n_blocks) * B:(k % n_blocks + 1) * B]
        fdl = np.roll(fdl, 1, axis=0)
        fdl[0] = np.fft.rfft(np.concatenate((prev, block)))
        out = np.tanh(np.fft.irfft((fdl * H).sum(axis=0))[B:])                       # reverb + soft limiter
        prev = block
        return out

    fifo_ok = affinity_ok = False
    mlock_ok = libc.mlockall(3) == 0                              # needs IPC_LOCK
    try:
        os.sched_setaffinity(0, {cfg["cpus"][i]}); affinity_ok = True
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(cfg["fifo_prio"])); fifo_ok = True
    except OSError as e:
        print(f"warning: affinity/SCHED_FIFO not set ({e})", file=sys.stderr)
    for k in range(cfg["warmup"]):
        job(k)
    if ready.wait() == 0:                                        # all processes ready: the last one sets the common start
        shared_t0.value = now_ns() + 2 * 10**9
    ready.wait()
    t0 = shared_t0.value

    n, period = cfg["jobs"], round(cfg["period_ms"] * 1e6)
    rows, next_k = [], 0
    gc.collect(); gc.freeze(); gc.disable()
    for k in range(n):
        rel = t0 + k * period
        if k < next_k:                                           # a release that passed during an overrun: skipped
            rows.append([inst, k, k % n_blocks, rel, "", "", "", "", "", "", 0, 1, 0])
            continue
        sleep_until(rel)
        s, c = now_ns(), time.thread_time_ns()
        job(k)
        cpu_ns, e = time.thread_time_ns() - c, now_ns()
        rows.append([inst, k, k % n_blocks, rel, s, e, cpu_ns, e - rel, s - rel, e - rel - period, int(e <= rel + period), 0, 0])
        while next_k < n and t0 + next_k * period < e:
            next_k += 1
    gc.enable()

    out = f"{cfg['output']}_{inst}"
    with open(out + ".csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["instance_id", "job_id", "frame_idx", "release_ns", "start_ns", "end_ns", "cpu_ns", "response_ns",
                    "wait_ns", "lateness_ns", "deadline_met", "skipped", "warmup"])
        w.writerows(rows)
    cpu_model = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), None)
    json.dump({"args": {**cfg, "instance_id": inst, "cpu": cfg["cpus"][i]}, "instance_id": inst, "mlockall_ok": mlock_ok,
               "sched_fifo_ok": fifo_ok, "affinity_ok": affinity_ok, "start_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "hostname": socket.gethostname(), "kernel_version": platform.release(), "cpu_model": cpu_model, "numpy": np.__version__},
              open(out + ".meta.json", "w"), indent=2)
    ran = np.array([r[6] for r in rows if r[6] != ""]) / 1e6
    print(f"[{inst}] {len(ran)} jobs run, {n - len(ran)} skipped; cpu_ms median={np.median(ran):.3f} "
          f"p99={np.percentile(ran, 99):.3f} max={ran.max():.3f}", flush=True)


if __name__ == "__main__":
    cfg = dict(CFG)
    for kv in sys.argv[1:]:                                      # key=value overrides, values as JSON (plain text stays a string)
        key, value = kv.split("=", 1)
        try:
            cfg[key] = json.loads(value)
        except ValueError:
            cfg[key] = value
    n = len(cfg["cpus"])
    ready, t0 = multiprocessing.Barrier(n), multiprocessing.Value("q", 0)
    procs = [multiprocessing.Process(target=run_instance, args=(cfg, i, ready, t0)) for i in range(n)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    sys.exit(any(p.exitcode for p in procs))
