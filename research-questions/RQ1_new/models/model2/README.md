# model2 — co-located reservation (SMT sibling)

**Question:** does the reservation firewall the target from **one reserved neighbour**
sharing its physical core?
**Expect:** execution-layer **break** — α = C/Q > 1, ~100% miss. A single co-tenant on
the sibling is enough.

## Run
```bash
./build.sh
bash node-prep/apply.sh model2
python calibrate.py model2
python generate_yaml.py model2
COLOCATE=1 ./run_job.sh model2   # retries until the neighbour lands on the target's SMT sibling
python result.py model2
```

Prereq: worker labelled `experiment-model=model2`.

**Why `COLOCATE=1`:** with only 2 reservations the SMT-blind driver would put them on
**separate** cores (no contention). `COLOCATE` retries placement until a neighbour is on
the target's sibling, so the two containers truly share one physical core.

Verify co-location (auditable per cell):
```bash
cat results/model2/soft/U0.5/placement.json   # -> "neighbour_on_sibling":"true"
```
If cells keep printing `no neighbour on target's sibling ... re-placing` and skip, raise
`PIN_ATTEMPTS=15 COLOCATE=1 ./run_job.sh model2`.
