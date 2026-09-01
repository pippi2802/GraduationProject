# model3 — unreserved interferer: SMT sibling vs separate core

**Question:** does a best-effort (unreserved) neighbour break a reserved RT task, and is
it the **SMT sharing** specifically? Sibling = same physical core; separate = the control.
**Expect:** sibling → ~1.9× C, ~100% miss. Separate → ~1.0×, ~0% miss (holds).

## Run
```bash
./build.sh
bash node-prep/apply.sh model3
python calibrate.py model3
python generate_yaml.py model3
INTF_PLACEMENT=sibling  ./run_job.sh model3                 # same physical core (breaks)
INTF_PLACEMENT=separate OUT_TAG=_sep ./run_job.sh model3    # different core (control, holds)
python result.py compare model3 model3_sep                  # overlay CDFs + C-inflation table
```

Prereq: worker labelled `experiment-model=model3`.

Proof of placement (per cell):
```bash
cat results/model3/soft/U0.5/placement.json   # target_RT_CPUSET, interferer_cpu, interferer_on_sibling
```

**Data-dependent variant (optional):** run the same experiment with the primes
workload (trial-division primality, genuinely data-dependent/early-exit control
flow, integer-divide/branch-predictor bound -- any model supports it). Its
intrinsic per-job cv is much higher than matmul's (~0.1-0.3 vs ~0.02-0.04), so
pass a looser CV_THRESHOLD:
```bash
CV_THRESHOLD=0.3 WORKLOAD=primes python calibrate.py model3
WORKLOAD=primes python generate_yaml.py model3
CV_THRESHOLD=0.3 INTF_PLACEMENT=separate OUT_TAG=_primes_sep ./run_job.sh model3    # on a SEPARATE core
python result.py model3_primes_sep
```
