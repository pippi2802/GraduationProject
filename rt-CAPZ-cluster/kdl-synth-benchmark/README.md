# kdl-synth-benchmark

First validation experiment for **KubeDeadline** — does **RT-DRA** (a Dynamic
Resource Allocation driver exposing Linux `SCHED_DEADLINE` / hierarchical CBS)
actually deliver reserved CPU budget and let a schedulable set of periodic
real-time tasks meet their deadlines, where **vanilla Kubernetes** (default CFS
with cpu requests/limits) fails under contention?

This replicates the first synthetic experiment from the KubeDeadline paper
(Samimi et al.): generate periodic task sets with **RandFixedSum**, size a
reservation `(Q, P, m)` per set via **MPR** analysis using **CARTS**, run each
set in two modes — **RT-DRA reservation** vs **vanilla** — under a best-effort
noisy neighbour, then compare deadline-miss ratios as a function of utilisation
`U`.

## Environment assumptions

- One Linux worker node: **Azure Standard D4s_v5** = 4 vCPU (2 physical cores ×
  2 hyperthreads), 16 GB RAM. Control plane elsewhere.
- Kernel patched with **H-CBS**; **RT-DRA driver installed and working** (a
  `(Q,P,m)` ResourceClaim already schedules on this cluster).
- Task sets are constrained to `m ≤ 2` cores and `U ≤ 1.8` for clean results on
  the 2-physical-core node. **No hyperthreading enable/disable logic here.**

## Layout

```
workload/        synthetic periodic RT task (C11, pthreads) + Dockerfile
interference/    best-effort stress-ng noisy neighbour + Dockerfile
gen/             RandFixedSum generator + CARTS (Q,P,m) wrapper + tasksets/
deploy/          ResourceClaim + pod templates (rtdra / vanilla / interference)
experiments/     run_all.sh — iterate tasksets x modes, collect JSONL
analysis/        parse.py (JSONL -> pandas), compare.py (miss-ratio vs U)
```

## 1. Build

```bash
# C workload
cd workload && make                 # produces ./rt-workload
docker build -t REGISTRY/kdl-workload:latest .

# interference image
cd ../interference
docker build -t REGISTRY/kdl-interference:latest .

# push both to your registry, then `docker push ...`
```

Python tooling:

```bash
pip install -r requirements.txt
```

## 2. Generate task sets + reservations

```bash
# RandFixedSum sets (defaults: 150 sets, n∈[4,12], U swept 0.6..1.8)
python gen/randfixedsum.py --count 150 --u-max 1.8

# attach (Q,P,m) via CARTS (falls back to analytic stub if CARTS not configured)
python gen/carts_wrapper.py --cap-cores 2
```

To use the real **CARTS** tool, build its jar and point the wrapper at it via
`CARTS_JAR` (the wrapper runs `java -jar <CARTS_JAR> <in.xml> MPR2 <out.xml>`):

```bash
# build the jar (needs a JDK + Ant)
cd ../carts/carts-dev && ant dist          # produces carts.jar

# generate reservations with real MPR analysis
export CARTS_JAR="$PWD/carts.jar"          # path may contain spaces
python gen/carts_wrapper.py --cap-cores 2  # reservations tagged source=carts
```

Optional env: `CARTS_JAVA` (java launcher, default `java`), `CARTS_MODEL`
(default `MPR2`). If `CARTS_JAR` is unset, a documented conservative analytic
stub sizes the interface (tagged `source=stub`) so the pipeline runs end-to-end.

## 3. Local smoke test (no cluster)

```bash
cd workload && make
# pick any generated set
./rt-workload --taskset ../gen/tasksets/set000_n*_U*.json \
              --jobs 200 --warmup 10 --out /tmp/metrics.jsonl \
              --mode rtdra --util 1.2 --cores-m 2 --interference none
python ../analysis/parse.py /tmp/metrics.jsonl --out /tmp/jobs.csv
```

This should yield well-formed JSONL with sane `exec_time_us` / `response_time_us`.

## 4. Run on the cluster

Provide the **real RT-DRA claim**: edit
[deploy/resourceclaim-rt.yaml](deploy/resourceclaim-rt.yaml) and replace the
placeholder schema with your working `(Q,P,m)` ResourceClaim
(`TODO: paste working claim`). Then:

```bash
NODE=<rt-worker-node> \
IMAGE=REGISTRY/kdl-workload:latest \
IMAGE_INTERF=REGISTRY/kdl-interference:latest \
INTERFERENCE=on \
bash experiments/run_all.sh
```

`run_all.sh` iterates every taskset × `{rtdra, vanilla}`: it injects the
taskset via a ConfigMap, applies the claim (rtdra only) + workload pod (+ a
best-effort interference pod), waits for completion, copies
`/out/metrics.jsonl` into `results/<mode>/<taskset>.jsonl`, then cleans up. It
prints a per-run line: `mode, n, U, miss_ratio, p99_resp_us`.

## 5. Analyse

```bash
python analysis/compare.py results --out-dir analysis_out
```

Produces:
- `miss_ratio_vs_U.png` — headline: miss ratio vs `U`, rtdra vs vanilla
- `schedulability.csv` — fraction of zero-miss task sets per mode per `U` bin
- `response_dist.png` — response-time distributions
- `per_taskset.csv` — per (mode, taskset) miss ratio + p99 response time

**Expectation:** with interference on, RT-DRA stays ≈ 0 misses for
CARTS-schedulable sets; vanilla's miss ratio rises with `U` / contention.

## Per-job metrics schema (JSONL)

One line per job, stable across phases:

```json
{
  "run_id": "rtdra-set017-u1.2", "mode": "rtdra", "taskset_id": "set017",
  "task_id": 3, "job_index": 540,
  "release_ts_ns": 0, "start_ts_ns": 0, "completion_ts_ns": 0,
  "exec_time_us": 4188, "response_time_us": 4399,
  "target_c_us": 4200, "period_t_us": 33000, "deadline_us": 33000,
  "overrun": false, "deadline_miss": false, "tardiness_us": 0,
  "budget_q_us": 9000, "period_p_us": 33000, "cores_m": 2,
  "util": 1.2, "n_tasks": 8, "interference": "on",
  "node": "rt-pool-0", "kernel": "hcbs"
}
```

- `overrun` = `exec_time_us > target_c_us` (cloud-induced exec inflation).
- `deadline_miss` = `completion_ts > release_ts + deadline_us`.
- `tardiness_us` = `max(0, completion_ts - (release_ts + deadline_us))`.

## Design notes / pitfalls handled

- Busy-loop is **not** optimized away (`volatile` sink + arithmetic barrier).
- `burn_cpu` targets CPU **time** by re-checking `CLOCK_THREAD_CPUTIME_ID`, not
  a fixed iteration count — robust to Azure frequency drift / CPU steal.
- **Absolute-time pacing** (`clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME)`);
  `EINTR` re-sleeps to the same target so tardiness is observable, never hidden.
- Metrics are flushed on `SIGTERM`/`SIGINT`, so `kubectl delete` still yields
  complete data.
- All nanosecond arithmetic is 64-bit.
- Vanilla uses the **same image, taskset, and job/warmup counts** as RT mode —
  the only difference is the absence of the reservation (fair comparison).
- The `Q/P/m` CLI flags are **labels only**; real enforcement is the RT-DRA
  claim.
