# validation

Online validation of the budgets under KubeDeadline: the budget Q* is given to the scheduler as the reservation, the
task runs, and the real misses are counted. For **both scenarios**, each on a VM that did not profile it
(multi-core on **worker6**, profiled on worker7; single-core on **worker7**, profiled on worker6), 50000 jobs per
instance, for the three tolerances p = 10^-1, 10^-2, 10^-3, each with and without interference (the memory enemy),
for both routes: 2 scenarios x 2 routes x 3 tolerances x 2 = 24 runs.

```
validation/
  budgets.csv           scenario, route, p, Q (ms), reservation runtime (us): the numbers behind the manifests
  make_manifests.py     writes the manifests from budgets.csv (python3, standard library only)
  manifests/
    multi_core/  route1/  p1e-1_none.yaml  p1e-1_memory.yaml  p1e-2_...  p1e-3_...   (6 files)
                 route2b/ the same 6 for Route 2b
    single_core/ route1/  and  route2b/                                              (6 files each)
  run_validation.sh     runs one scenario's manifests one after the other and saves the data here
  results/<scenario>/   <route>/<p>_<interference>/{instance0,instance1}.{csv,meta.json}, manifest.yaml,
                        plus validation.log and summary.tsv   (git-ignored)
```

## Run it (on the control plane)

The two scenarios use different VMs, so start both at the same time. Each takes about 7.2 h (12 runs of ~36 min).

```bash
cd ~/GraduationProject/research-questions/RQ2
DRY_RUN=1 validation/run_validation.sh multi_core           # prints the plan, touches nothing (also single_core)
setsid nohup validation/run_validation.sh multi_core  > /dev/null 2>&1 < /dev/null &
setsid nohup validation/run_validation.sh single_core > /dev/null 2>&1 < /dev/null &
tail -f validation/results/multi_core/validation.log        # and single_core
```

`run_validation.sh <scenario> route1` (or `route2b`) runs only that route: 6 runs, about 3.6 h. The order is p1e-3
first, then p1e-2, then p1e-1; inside each, route1 then route2b, and each run without then with interference.

For every run it applies the manifest, starts the memory enemy first when the file name ends in `_memory` (cpus 3,0
for multi-core, 2,3,0 for single-core, confirmed to be really running), polls the pod until it finishes, pulls the
CSV and meta.json of every instance through the node-prep agent, checks them (rows, real-time flags, job count in
meta.json), prints the number of misses to the log, deletes the run's objects, stops the enemy (confirmed) and
settles for 10 s.

- **Safe to restart**: a collected run (`.done` in its folder) is skipped. After a crash, just start it again.
- A failed run is retried once, then recorded as FAILED (`summary.tsv`) and the rest goes on.
- An exit trap stops the enemy if the script is killed. The script stops at the start, doing nothing, if the agent
  of the VM is not found, the node lacks `experiment-model=rq2`, an `rq2-enemy` is already running, or a pod of the run exists.
- The agent is the one running on the VM (`spec.nodeName`), so a second agent of the same namespace, for example on
  a node that is switched off (worker0 shares the namespace of worker7), does not matter.
- The wait polls the pod phase every 30 s (not `kubectl wait`, whose watch can close early).

## Before starting

1. Pull the repo on the control plane.
2. worker6 and worker7 up and Ready, with the isolation of the profiling VMs and the RT budget seeded on each (the
   seed output must show at least 0.63, the largest Q*/T here; a reboot zeroes it). The enemy binary installed
   (`/usr/local/bin/rq2-enemy`) and at least 3 GB free on both.
3. Nothing else running in namespace `rq2` (both scenarios use it, with different pod names).
4. The label `rq2-isolation=worker7` on `rt-k8s-worker-7` and an agent running there.

## Changing the budgets, the VM or the jobs

Edit `budgets.csv` (the numbers come from the notebook: Alpha Drift section, "budgets Q* per deployment", the `dep`
table, maximum over the instances, runtime rounded **up** to the microsecond), or `SCEN` (node) / `JOBS` at the top of
`make_manifests.py`, then run `python3 validation/make_manifests.py`. A different VM also needs `NODE` /
`NODE_PREP_NS` for the script.

The current numbers are from a notebook run with a bootstrap of 100 and worker0 excluded from the drift pool;
a run with 300 resamples changes them in the third decimal.

## Not covered here

The check that the server's replenishment is aligned with the task's releases (done in the KubeDeadline/HCBS
implementation), the analysis of the results in the notebook, and the further workloads with different sensitivity
to interference.
