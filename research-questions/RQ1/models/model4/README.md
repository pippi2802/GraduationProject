# model4 — intra-reservation multithread (batch of 2, physical cores only)

**Question:** model1 shows a single H-CBS reservation delivers bounded R/tardiness
for a sequential, single-threaded task. Does that guarantee survive when the
reservation's own workload is split across **two threads running concurrently**
on two of its own claimed cores, instead of contention from an external
competitor (model3's question)?

**Design:** target claims `count: 2`. Every period releases a batch of 2
independent fixed-K jobs — one pthread per claimed cpu, dispatched together,
joined, logged as **one row per batch** (same `jobs.csv` schema as every other
model: `C_cputime_us` = the critical-path thread's cputime, `nonvol_ctxt` =
summed across both threads). The claimed pair is always forced onto two
**distinct physical cores** — never two SMT siblings of one core — by
run_job.sh's placement retry (`target_threads: 2` in config.yaml). No sibling
arm: that axis is model3's, and was the single biggest source of debugging
pain there (races, SIGSTOP hacks) — deliberately out of scope here.

Compare directly against model1 at matched U: same metrics, same statistical
treatment, one question — does going from 1 thread/1 core to 2 threads/2
cores *within the same reservation* preserve predictability, or does
something (parallel budget accounting, thread dispatch/join overhead) degrade
the tail.

## Run
```bash
IMAGE=pippina2/rq1-probe:v3 ./build.sh   # own tag -- guarantees a fresh pull on
                                          # model4's node; models 1-3 keep their
                                          # already-cached v2 untouched either way
bash node-prep/apply.sh model4
python calibrate.py model4                       # matmul; existing k_table.json is
                                                   # reusable (same per-core Q/P formula
                                                   # as before) but re-verify after any
                                                   # node reboot/reallocation
python generate_yaml.py model4
./run_job.sh model4 soft
./run_job.sh model4 tight

CV_THRESHOLD=0.3 WORKLOAD=primes python calibrate.py model4  # primes: genuinely
                                                   # data-dependent (early-exit), so
                                                   # intrinsic cv is much higher than
                                                   # matmul's -- pass a looser threshold
WORKLOAD=primes python generate_yaml.py model4
CV_THRESHOLD=0.3 WORKLOAD=primes ./run_job.sh model4 soft
CV_THRESHOLD=0.3 WORKLOAD=primes ./run_job.sh model4 tight

python result.py model4                           # per-model summary/figures
python result.py compare model4 model1            # direct model4-vs-model1 comparison
```

Prereq: worker labelled `experiment-model=model4`.

Ground truth per cell (proves the pair actually landed on distinct physical
cores, not just that the pod is Ready):
```bash
cat results/model4/soft/U0.1/placement.json
# target_RT_CPUSET should be two cpus (e.g. "2,3") that are NOT each other's
# SMT sibling -- run_job.sh already rejects+retries any landing that isn't,
# this is just the audit trail.
```

matmul.c's batch/multithread mode is `--threads N --cpu-list <c0,c1,...|env>`
(`env` reads `RT_CPUSET`, the same var `--cpu env` already used); `--threads 1`
(every other model) is byte-for-byte the original single-thread path.
