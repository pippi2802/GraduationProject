# common/kernel — shared deterministic matrix-multiply probe (RQ1 workload)

**Single workload for `model1_1`, `model2`, `model3`, `model4`** (model1 is
independent and does NOT use this). All four run the *same* binary/image with
different reservations, topology and neighbours — only the configuration differs,
so any change in the measured times is attributable to the environment, not the
workload.

A **fixed** dense double-precision matrix multiply `C = A × B` (`M×M`, default
`M=48` so A,B,C fit in L1/L2), with A,B generated **once** from a fixed seed and
**reused every job**. The per-job compute demand is tuned by the repetition count
**K** (each model's `config.yaml → calibration`), never by data. Data-independent
control flow + tiny in-cache working set ⇒ execution time **C** has very low
intrinsic variance (target CV < 2% on an isolated core), so any inflation of the
response time **R** is the cloud environment's signature.

## Two clocks (the delay decomposition)
- **C** = `CLOCK_THREAD_CPUTIME_ID` delta over the compute — CPU time actually
  consumed; does **not** advance during steal/preemption ⇒ execution layer.
- **R** = wall (`CLOCK_MONOTONIC`) `finish − release` ⇒ the guarantee.
- `delay = R − C`, split into `dispatch_latency = start − release` and
  `mid_job_preempt = (finish − start) − C`.

> Clock note: the periodic release is driven by `clock_nanosleep`, which cannot
> use `CLOCK_MONOTONIC_RAW`, so the wall clock is `CLOCK_MONOTONIC` (its sleepable
> sibling). Over a bounded cell the difference is NTP slew only and does not affect
> any intra-job delta. `C` is `CLOCK_THREAD_CPUTIME_ID` as specified.

## Per-job CSV columns
`job_index, release_us, start_us, finish_us, C_cputime_us, R_wall_us, delay_us,
dispatch_latency_us, mid_job_preempt_us, slack_us, deadline_miss, tardiness_us,
nonvol_ctxt, K_reps, matrix_M` (`nonvol_ctxt` = involuntary context switches during
the job, from `getrusage(RUSAGE_THREAD)`).

## Build
- **Native (for calibration on the node):** `make` → `./matmul`.
- **Container image (Docker Hub):** `./build.sh` (pushes `pippina2/model1-kernel:v0.1.0`
  by default; override with `IMAGE=...`). Needs `docker login`.

> The image is historically named `model1-kernel` (first pushed by `model1_1`);
> the name is kept stable so already-validated pulls keep working. Every
> participating model's `config.yaml` references this same `image.full_ref`.

## Run (standalone)
```bash
./matmul --M 48 --K 1000 --period-us 10000 --n-jobs 5000 --warmup 200 \
         --priority 90 --cpu env --logfile out.csv
```
`--cpu env` reads `RT_CPUSET` (KubeDeadline sets it); `--priority 0` disables the
SCHED_FIFO request (C is still valid). SCHED_FIFO / `mlockall` are best-effort and
warn-but-continue without `CAP_SYS_NICE` / `IPC_LOCK`.
