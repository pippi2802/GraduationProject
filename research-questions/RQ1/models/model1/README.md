# model1 — clean baseline (no co-runner)

**Question:** does an isolated RT reservation meet its deadline with no contention?
**Expect:** guarantee **holds** — soft ~0% miss; tight a sub-1% cloud-jitter floor.

## Run
```bash
./build.sh                       # once: build + push the probe image (:v2)
bash node-prep/apply.sh model1   # pin frequency + start the results agent
python calibrate.py model1       # -> models/model1/k_table.json  (freq must be pinned)
python generate_yaml.py model1   # -> models/model1/generated/<scale>/U<u>.yaml
./run_job.sh model1              # both scales (or: ./run_job.sh model1 soft)
python result.py model1          # -> results/model1/summary.csv + figures/
```

Prereq: a worker labelled `experiment-model=model1`
(`kubectl label node <node> experiment-model=model1 --overwrite`).

Optional: pin every cell to one core with `PIN_RTCPU=2 ./run_job.sh model1`.
