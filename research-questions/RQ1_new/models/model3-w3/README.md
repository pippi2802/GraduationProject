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

**Memory-contention variant (optional):** run the same experiment with the memory/LLC
workload to test the cache/bandwidth boundary (any model supports it):
```bash
WORKLOAD=ptrchase BUF_KB=131072 python calibrate.py model3
WORKLOAD=ptrchase BUF_KB=131072 python generate_yaml.py model3
INTF_PLACEMENT=separate OUT_TAG=_mem_sep ./run_job.sh model3    # memory hog on a SEPARATE core
python result.py model3_mem_sep
```
