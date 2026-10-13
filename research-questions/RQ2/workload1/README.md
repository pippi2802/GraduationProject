# Periodic RT workload (KubeDeadline experiments)

A synthetic "video frame processor" task, single-threaded, run under
`SCHED_FIFO` with CPU affinity. It never uses `SCHED_DEADLINE` itself — the
reservation is provided externally by KubeDeadline's CBS.

- `rt_video.py` — the periodic app. One process = one task.
- `launch.py` — starts one `rt_video.py` process per instance (per RT core),
  all sharing a common `--start-at` time base. Local/manual testing only
  (not used for real k8s runs — see `pods/`).
- `configs/single_core.json` / `configs/multi_core.json` — instance lists
  for `launch.py`.
- `pods/single_core_pod.yaml` / `pods/multi_core_pod.yaml` — the real
  KubeDeadline pod specs; edit the values noted in their header comments
  and `kubectl apply -f` them.
- `videos/` — the clip (`prepare_clip.sh` + the prepared `.mp4`, git-ignored).
- `Dockerfile` — builds `rq2-workload:latest`, the image the pod specs use.

Platform: Azure (SMT off — see `research-questions/RQ2/setup/` for the
cluster IaC). `cpu0` is housekeeping; the rest are isolated RT cores.
Single-core = 1 instance on 1 RT core; multi-core = one instance per core.

## Install (local testing)

```bash
pip install -r ../requirements.txt
```

## 1. Prepare the clip (once)

```bash
videos/prepare_clip.sh path/to/sintel_trailer_2k_720p24.tar.gz
```

See `videos/prepare_clip.sh`'s header and the top-level README for details
(licence, excerpt, provenance sidecar).

## 2. Calibrate: choose `--work` for a target execution time

```bash
python3 rt_video.py --calibrate --calib-jobs 200 --work 1 \
    --input videos/sintel_720p_600.mp4 --width 1280 --height 720 --frames 600
```

Or let it search for a target median CPU time:

```bash
python3 rt_video.py --calibrate --target-cpu-ms 15 \
    --input videos/sintel_720p_600.mp4 --width 1280 --height 720 --frames 600
```

Target: baseline median ~30-50% of the period (41.667ms at the clip's
native 24fps), longest job under memory-enemy stress still clearly below it.

## 3. Local single-core run (no k8s)

```bash
python3 rt_video.py --cpu 1 --fifo-prio 50 \
    --period-ms 41.667 --work 1 --input videos/sintel_720p_600.mp4 \
    --width 1280 --height 720 --frames 600 \
    --jobs 2000 --overrun skip \
    --instance-id instance0 --output /tmp/rq2_smoke/instance0.csv
```

(`sched_setaffinity`/`SCHED_FIFO` need `CAP_SYS_NICE`/root; without it the
app warns and keeps running at normal priority, e.g. on a laptop. For a
real run, use `pods/single_core_pod.yaml` instead — see below.)

## 4. Local multi-core run (via launch.py, no k8s)

```bash
python3 launch.py configs/multi_core.json
```

## 5. Noise-floor measurement (empty job)

Measures the runtime's own overhead/jitter with no real work in the loop:

```bash
python3 rt_video.py --cpu 1 --fifo-prio 50 --empty-job \
    --period-ms 41.667 --jobs 2000 \
    --instance-id instance0 --output /tmp/rq2_smoke/empty_job_instance0.csv
```

## 6. A real run, under KubeDeadline

```bash
docker build -f Dockerfile -t rq2-workload:latest ..    # from workload/, context is RQ2 root
# push/load rq2-workload:latest onto the cluster's registry/nodes, then:
kubectl apply -f pods/single_core_pod.yaml
# or, for two synchronized instances:
kubectl apply -f pods/multi_core_pod.yaml   # fill in --start-at first, see its header comment
```

Collect results from wherever `hostPath` in the pod spec points
(default `/var/lib/rq2/results/...` on the node), analyze with
`../analysis/analyze.py`.

## 7. Analyze / replay

See `../analysis/README.md` (or just `../analysis/analyze.py --selftest`
and `../analysis/replay.py --selftest`).
