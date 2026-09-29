# Periodic RT workload (KubeDeadline experiments)

A synthetic "video frame processor" task, single-threaded, run under
`SCHED_FIFO` with CPU affinity. It never uses `SCHED_DEADLINE` itself — the
reservation is provided externally by KubeDeadline's CBS.

- `rt_video.py` — the periodic app. One process = one task.
- `launch.py` — starts one `rt_video.py` process per instance (per RT core),
  all sharing a common `--start-at` time base.
- `analyze.py` — per-instance + aggregated timing report from CSV logs.
- `replay.py` — replays a measured `cpu_ns` trace under a hard CBS budget Q,
  for a range of candidate Q, to build a budget-risk curve.

Platform assumed: Azure D8s_v5 (SMT off, 4 vCPUs = 4 physical cores).
`cpu0` is housekeeping; `cpu1`-`cpu3` are isolated RT cores. Single-core =
1 instance on 1 RT core; multi-core = 2-3 instances, one per RT core.

## Install

```bash
pip install -r requirements.txt
```

## 1. Calibrate: choose `--work` for a target execution time

```bash
python3 rt_video.py --calibrate --calib-jobs 200 --work 1 \
    --width 1280 --height 720 --frames 30
```

Or let it search for a target median CPU time:

```bash
python3 rt_video.py --calibrate --target-cpu-ms 5 \
    --width 1280 --height 720 --frames 30
```

## 2. Single-core run

```bash
python3 rt_video.py --cpu 1 --fifo-prio 50 \
    --period-ms 33.3 --work 3 --width 1280 --height 720 --frames 30 \
    --jobs 100000 --overrun skip \
    --instance-id instance0 --output results/single_core_instance0.csv
```

(`sched_setaffinity`/`SCHED_FIFO` need `CAP_SYS_NICE`/root; without it the
app warns and keeps running at normal priority, e.g. on a laptop.)

## 3. Multi-core run (via launch.py)

```bash
python3 launch.py configs/multi_core.json
```

Edit `configs/multi_core.json` / `configs/single_core.json` for your
`cpu`/`period_ms`/`work`/`jobs` values; one instance per RT core.

## 4. Noise-floor measurement (empty job)

Measures the runtime's own overhead/jitter with no real work in the loop:

```bash
python3 rt_video.py --cpu 1 --fifo-prio 50 --empty-job \
    --period-ms 33.3 --jobs 100000 \
    --instance-id instance0 --output results/empty_job_instance0.csv
```

## 5. Analyze

```bash
python3 analyze.py results/*.csv --meta results/*.meta.json \
    --output results/analysis.json
python3 analyze.py --selftest
```

## 6. Budget-risk curve (replay)

```bash
python3 replay.py results/single_core_instance0.csv --period-ms 33.3 \
    --q-min-ms 1 --q-max-ms 15 --q-steps 30 \
    --output results/replay.csv --plot results/replay.png \
    --target-miss-rate 0.01 --max-consecutive 3 --mk 48,50
python3 replay.py --selftest
```

## Docker

```bash
docker build -t kubedeadline-rt-workload .
docker run --rm -v $PWD/results:/results -v $PWD/configs:/config \
    kubedeadline-rt-workload /config/multi_core.json
```

Plug the resulting image into your KubeDeadline pod spec; the container
entrypoint is `launch.py <config path>`.
