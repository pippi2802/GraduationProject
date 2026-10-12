# Online validation of the segmentation workload: GEV budgets against observed-data budgets

Two sets of budgets for the same workload, both given to KubeDeadline as the reservation, the task run under them, and the real misses counted, to see which
way of getting C_p gives the better budget.

| set | C_p comes from | file |
|---|---|---|
| `empirical` | the observed data: (1-p) quantile of C with the upper 95 % bound of a moving-block bootstrap | `budgets_empirical.csv` |
| `gev` | the tail estimation: GEV fitted to the block maxima (block 500) with the extremal index at that p; a point estimate, without confidence margin | `budgets_gev.csv` |

Both files are exported by `analysis/analysis_workload2.ipynb` (section 5.1b, `results/budgets_workload2_<source>.csv`); set `CP_SOURCE` in its configuration cell to
`"empirical"` or `"gev"` and run it. The two sets use the same chain otherwise (Route 1 and Route 2 with their α_cores,platform, α_drift computed from the same kind of C_p).
Route 3 (high-water mark) needs Q/T = 1.03–1.07 and is not admitted by the driver, so it has no run.

**24 runs per scenario, 48 in all**: for each estimator the routes Route 1 and Route 2 at p = 1e-1, 1e-2, 1e-3, each without and with the memory enemy. 10000 jobs of 100 ms per
instance (16.7 min); about 20 min a run with the pod start, so about 8 h per scenario. Each scenario runs on the node that did not profile it (multi-core on
`rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`), so the two run at the same time.

```
budgets_empirical.csv, budgets_gev.csv    scenario, route, p, runtime_us, period_us   <- edit or re-export these to change a budget
make_manifests.py    python3 make_manifests.py  (standard library only) writes everything below; budgets with Q/T above 0.95 are skipped
pods/<estimator>/<scenario>/<route>/<p>_<none|memory>.yaml    self-contained: RtClaimParameters + ResourceClaimTemplate + Pod
runs.csv             one line per run: pod file, node, enemy cpus, reservation, where the files appear on the node, where to save them
step5_input/<estimator>/budgets.csv     the same budgets in the format step 5's validate.py reads
results/<estimator>/<scenario>/<route>/<p>_<interference>/instance<N>.csv    where the results of each run are saved (git-ignored)
results/logs/<scenario>/validation.log, summary.tsv                           progress and outcome of every run
```
The pod runs `python3 run.py configs/<scenario>.json period_ms=100 jobs=10000 output=/results/<run id>` from image `pippina2/rq2-seg:v2` and writes
`/var/lib/rq2/results/seg_validation/<run id>_instance<N>.csv` on the node. The memory enemy is not in the pod: `run_validation.sh` starts it on the node around the runs
whose file ends in `_memory.yaml` (cpus 3,0 for multi-core, 2,3,0 for single-core, buffer 2662400 KB, as in the profiling).

## Run all of it (on the control plane, from this folder)
```bash
DRY_RUN=1 ./run_validation.sh                                  # the plan: 24 runs per scenario, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &         # both scenarios at the same time: about 8 h
tail -f results/logs/single_core/validation.log                # progress; also results/logs/multi_core/validation.log
./run_validation.sh --scenario single_core --estimator gev     # only one scenario / estimator / route (--route route1|route2b)
pkill -TERM -f "[r]un_validation.sh"                           # stop it (Ctrl-C also works); the enemies are stopped too
```
Order: p = 1e-3 first, then 1e-2, then 1e-1; inside each, the empirical set then the GEV set, route1 then route2b, without then with the memory enemy. Everything else
(stray-enemy check by name, slice period check, retry, `.done` markers, restart) works as in `workload3/validation/run_validation.sh`: a collected run is skipped when you start it again.
It refuses to start if a pod of this validation or of the profiling (`rq2-single-instance0`, `rq2-multi`) exists, or an `rq2-enemy` is running on a node.
Prerequisites: kubectl, python3, the enemy installed on both nodes (`../../procedure/step2_profiling/install_enemy.sh <agent-ns> <node>`), `../../stress1/campaign_{start,stop}_enemies.sh`.

## Check the results (step 5), once per set
```bash
cd ../../procedure/step5_online_validation
python3 validate.py check --step4 ../../workload2/validation/step5_input/empirical --results ../../workload2/validation/results/empirical
python3 validate.py check --step4 ../../workload2/validation/step5_input/gev       --results ../../workload2/validation/results/gev
```
Each prints, per route and p, P(C ≤ B*) (valid when ≥ 1 − p), the over-budget against the (1−p) quantile of the run itself, and the deadline-miss rate. The two tables side
by side answer the question: which set meets p, and at which cost in reserved utilisation Q/T.
Note: with 10000 jobs there are only about 10 expected exceedances at p = 1e-3, so a pass at that p is weak evidence; p = 1e-2 and 1e-1 have 100 and 1000.

## Changing a budget
Edit (or re-export) the csv, run `python3 make_manifests.py`, and delete the results of the runs that changed.
