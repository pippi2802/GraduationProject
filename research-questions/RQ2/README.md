# RQ2: deriving KubeDeadline reservation parameters from measurement

Measure a periodic real-time video-processing task under interference on
the real cluster, and use that to derive/validate a CBS reservation
(budget `Q`, period `T`) under KubeDeadline.

```
workload/     the task itself: rt_video.py, its video clip, and the pod
              specs that deploy it under a KubeDeadline reservation
stress/       the two interference generators (cache/memory) + the script
              that runs them in sequence + the script that verifies they
              actually stress the right thing
analysis/     turns the CSVs from workload/ and stress/ into numbers/plots
results/      everything the above two produce (git-ignored)
setup/        cluster provisioning (Bicep) - not part of the RQ itself
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make -C stress
```

## 1. Prepare the clip

```bash
workload/videos/prepare_clip.sh path/to/sintel_trailer_2k_720p24.tar.gz
```

600-frame excerpt of the Sintel trailer (Blender Foundation, CC BY 3.0),
starting at source frame 300, full 1280x720 (no resize), native 24fps
(`T = 41.667ms`). Writes `workload/videos/sintel_720p_600.mp4` plus a
`.clip_metadata.json` sidecar (sha256, measured resolution/fps) — that
JSON, not this README, is the citable record for the thesis.

## 2. Check the enemies actually stress the right thing

```bash
stress/verify_targets.sh --enemy stress/enemy --cpu 2 \
    --cache-size-kb <real LLC size> --memory-size-kb <10x LLC size>
stress/enemy_effectiveness.sh --victim stress/victim --enemy stress/enemy \
    --victim-cpu 1 --enemy-cpus 2,3 \
    --cache-size-kb <LLC> --memory-size-kb <10x LLC> \
    --output results/enemy_effectiveness.csv
```

See `stress/README.md`. Do this once per platform, before trusting any
profiling data collected on it.

## 3. Smoke-test the workload itself

Directly on a worker node (needs root for `SCHED_FIFO`/`mlockall`):

```bash
cd workload
python3 rt_video.py --calibrate --calib-jobs 100 --work 1 \
    --input videos/sintel_720p_600.mp4 --width 1280 --height 720 --frames 600
sudo python3 rt_video.py --cpu 1 --fifo-prio 50 --period-ms 41.667 --work 1 \
    --input videos/sintel_720p_600.mp4 --width 1280 --height 720 --frames 600 \
    --jobs 2000 --overrun skip --instance-id smoketest \
    --output /tmp/rq2_smoke/instance0.csv
cat /tmp/rq2_smoke/instance0.meta.json   # mlockall_ok / sched_fifo_ok / affinity_ok must all be true
```

See `workload/README.md` for the full walkthrough, including the real
KubeDeadline pod deployment (`workload/pods/`).

## 4. Analyze

```bash
python3 analysis/analyze.py results/*.csv --meta results/*.meta.json --output results/analysis.json
```

See `analysis/README.md`.
