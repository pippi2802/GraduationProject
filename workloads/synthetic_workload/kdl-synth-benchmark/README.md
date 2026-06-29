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

## 1. Build & push the images

The workload image must be **rebuilt and pushed whenever the C source under
`workload/src/` changes** (the node caches `:latest`; the workload pods use
`imagePullPolicy: Always` so a fresh push is always pulled).

```bash
# C workload  (rebuild + push after any workload/src change)
cd workload
docker build -t docker.io/pippina2/kdl-workload:latest .
docker push  docker.io/pippina2/kdl-workload:latest

# interference image  (rarely changes)
cd ../interference
docker build -t docker.io/pippina2/kdl-interference:latest .
docker push  docker.io/pippina2/kdl-interference:latest
```

Python tooling (analysis only, on your laptop):

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

The full pipeline spans three machines. Do them in order.

### 4a. Build VM — rebuild & push the workload image

```bash
cd ~/GraduationProject && git pull
cd rt-CAPZ-cluster/kdl-synth-benchmark/workload
docker build -t docker.io/pippina2/kdl-workload:latest .
docker push  docker.io/pippina2/kdl-workload:latest
```

### 4b. Control-plane node — pull the latest scripts/templates

```bash
cd ~/GraduationProject && git pull
cd rt-CAPZ-cluster/kdl-synth-benchmark
```

### 4c. Clean up any leftovers from a previous run

```bash
pkill -f run_all.sh 2>/dev/null
kubectl -n kdl-bench delete pods --all --force 2>/dev/null
```

### 4d. Quick smoke test (~1-2 min, foreground)

Verifies the whole path before committing to the long sweep. `MAX_SETS` caps the
number of task sets; `JOBS` shortens each run.

```bash
# vanilla, 2 sets, short runs, no interference
MAX_SETS=2 MODES="vanilla" JOBS=50 WARMUP=10 COOLDOWN=2 INTERFERENCE=off \
  bash experiments/run_all.sh

# rtdra smoke (verifies the ResourceClaim path)
MAX_SETS=2 MODES="rtdra" JOBS=50 WARMUP=10 COOLDOWN=2 INTERFERENCE=off \
  bash experiments/run_all.sh
```

Verify it worked (numbers, **not** `nan`; no `cp failed`):

```bash
ls -la results/vanilla/                 # non-empty .jsonl files
tail -1 results/vanilla/set*.jsonl      # last line = {"record":"summary",...,"steal_pct":...}
```

The `summary` line is proof the **new** binary is running.

### 4e. Full sweep

```bash
# all task sets x {rtdra, vanilla}, interference on; runs for hours -> nohup
NODE=rt-cluster-worker-0 \
IMAGE=docker.io/pippina2/kdl-workload:latest \
IMAGE_INTERF=docker.io/pippina2/kdl-interference:latest \
MODES="rtdra vanilla" INTERFERENCE=on \
  nohup bash experiments/run_all.sh > /tmp/run.log 2>&1 &

tail -f /tmp/run.log                    # watch progress
kubectl -n kdl-bench get pods -w        # watch pods
```

**Tunable env knobs:** `MAX_SETS` (0 = all), `JOBS` (jobs per run, default 1000),
`WARMUP`, `MODES` (`"rtdra vanilla"`), `INTERFERENCE` (`on|off`), `COOLDOWN`,
`TIMEOUT`, `NODE`, `IMAGE`, `IMAGE_INTERF`.

`run_all.sh` iterates every taskset × mode: it injects the taskset via a
ConfigMap, applies the claim (rtdra only) + workload pod (+ a best-effort
interference pod), waits for completion, captures `/out/metrics.jsonl` **from the
pod logs** into `results/<mode>/<taskset>.jsonl`, then cleans up. It prints a
per-run line: `mode, n, U, miss_ratio, p99_resp_us`.

## 5. Analyse

```bash
python analysis/compare.py results --out-dir analysis_out
```

Produces:
- `miss_ratio_vs_U.png` — **G2** headline: miss ratio vs `U`, rtdra vs vanilla
- `supply_delay_vs_U.png` — **G1**: p99 supply delay (ready-but-off-CPU) vs `U`
- `schedulability.csv` — fraction of zero-miss task sets per mode per `U` bin
- `response_dist.png` — response-time distributions
- `per_taskset.csv` — per (mode, taskset): miss ratio, p99 response, p99 wait,
  preempt, and run `steal_pct`

stdout tables: G2 miss ratio, schedulability, G1 supply delay, host CPU steal %,
and `corr(steal_pct, miss_ratio)`.

**Expectation:** with interference on, RT-DRA stays ≈ 0 misses for
CARTS-schedulable sets; vanilla's miss ratio rises with `U` / contention.

## Metrics schema (JSONL)

Each run file has **one line per job** (`record:"job"`) plus **one trailing
summary line** (`record:"summary"`).

Per-job line:

```json
{
  "record": "job", "run_id": "rtdra-set017-u1.2", "mode": "rtdra",
  "taskset_id": "set017", "task_id": 3, "job_index": 540,
  "release_ts_ns": 0, "start_ts_ns": 0, "completion_ts_ns": 0,
  "exec_time_us": 4188, "response_time_us": 4399,
  "wait_time_us": 211, "preempt_us": 12,
  "target_c_us": 4200, "period_t_us": 33000, "deadline_us": 33000,
  "overrun": false, "deadline_miss": false, "tardiness_us": 0,
  "budget_q_us": 9000, "period_p_us": 33000, "cores_m": 2,
  "util": 1.2, "n_tasks": 8, "interference": "on",
  "node": "rt-pool-0", "kernel": "hcbs"
}
```

Run-level summary line:

```json
{
  "record": "summary", "run_id": "rtdra-set017-u1.2", "mode": "rtdra",
  "taskset_id": "set017", "steal_pct": 0.42, "steal_us": 12345,
  "wall_us": 33000000, "iters_per_us": 277.9, "n_tasks": 8, ...
}
```

**G2 (deadline guarantee):**
- `deadline_miss` = `completion_ts > release_ts + deadline_us`.
- `tardiness_us` = `max(0, completion_ts - (release_ts + deadline_us))`.
- `overrun` = `exec_time_us > target_c_us` — **demand inflation** (cache/memory
  contention makes the same work cost more CPU).

**G1 (supply guarantee):**
- `wait_time_us` = `response_time_us - exec_time_us` — time the job was **ready
  but off-CPU** (supply not delivered).
- `preempt_us` — off-CPU time **during** the burn (pure starvation).
- `steal_pct` (summary) — % host-stolen CPU over the run, from `/proc/stat`; the
  **cloud cause** of G1 breakage (hypervisor vCPU steal).

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
