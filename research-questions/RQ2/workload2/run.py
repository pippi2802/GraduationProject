#!/usr/bin/env python3
"""Preprocessing and execution of the segmentation task on the worker. No training code, no TensorFlow.

    python3 run.py configs/single_core.json [key=value ...]      e.g. jobs=100 n_images=100

Start-up (not timed): load every picture of the folder (or the first `n_images`), resize them to the model input, keep them in RAM.
Then one job per picture, one at a time on one thread: copy the picture to the input buffer, run the network.
  period_ms = 0: continuous flow, the next picture is handed over the instant the previous one has finished.
  period_ms > 0: one picture released every period (overrun "skip" drops the releases that passed meanwhile).
Several `cpus` = one process per cpu, same start time. Output: <output>_instance<i>.csv (columns as in workload/rt_video.py,
cpu_ns = thread CPU time of the job) and <output>_instance<i>.meta.json.
"""
import csv, ctypes, ctypes.util, gc, json, multiprocessing, os, platform, socket, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1")

import cv2
import numpy as np
import onnxruntime as ort

cv2.setNumThreads(1)
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


def preprocess(cfg, h, w):
    """all pictures of the folder (or the first n_images), resized to the model input: uint8 [N, H, W, 3] RGB (as in train.py)"""
    files = sorted(f for f in os.listdir(cfg["images"]) if f.lower().endswith(".jpg"))[: cfg.get("n_images")]
    pics = np.empty((len(files), h, w, 3), dtype=np.uint8)
    for k, f in enumerate(files):
        img = cv2.resize(cv2.imread(os.path.join(cfg["images"], f), cv2.IMREAD_REDUCED_COLOR_2), (w, h), interpolation=cv2.INTER_AREA)
        pics[k] = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return pics


def run_instance(cfg, i, ready, shared_t0):
    inst = f"instance{i}"
    so = ort.SessionOptions()
    so.intra_op_num_threads = so.inter_op_num_threads = 1       # one thread: no pool next to the pinned FIFO thread
    so.add_session_config_entry("session.intra_op.allow_spinning", "0")
    sess = ort.InferenceSession(cfg["model"], so, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    _, h, w, _ = sess.get_inputs()[0].shape
    pics = preprocess(cfg, h, w)
    x = np.zeros((1, h, w, 3), dtype=np.float32)

    def job(k):
        np.copyto(x[0], pics[k % len(pics)], casting="unsafe")    # uint8 picture -> float32 input
        sess.run(None, {name: x})

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
            rows.append([inst, k, k % len(pics), rel, "", "", "", "", "", "", 0, 1, 0])
            continue
        if period:
            sleep_until(rel)
        s, c = now_ns(), time.thread_time_ns()
        job(k)
        cpu_ns, e = time.thread_time_ns() - c, now_ns()
        prev_end = e
        rows.append([inst, k, k % len(pics), rel, s, e, cpu_ns, e - rel, s - rel,
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
    json.dump({"args": {**cfg, "instance_id": inst, "cpu": cpu}, "instance_id": inst, "input_shape": [h, w],
               "start_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "hostname": socket.gethostname(),
               "kernel_version": platform.release(), "cpu_model": cpu_model, "onnxruntime": ort.__version__},
              open(out + ".meta.json", "w"), indent=2)
    ran = np.array([r[6] for r in rows if r[6] != ""]) / 1e6
    print(f"[{inst}] {len(ran)} jobs run, {n - len(ran)} skipped; cpu_ms median={np.median(ran):.2f} "
          f"p99={np.percentile(ran, 99):.2f} max={ran.max():.2f}", flush=True)


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1]))
    for kv in sys.argv[2:]:                                      # optional overrides: run.py cfg.json jobs=100 n_images=100
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
