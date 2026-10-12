# Online validation, procedure 2, iteration 0 (segmentation workload)

The budgets of `budgets.csv` come from `analysis_procedure2/analysis_workload2.ipynb` (section 6.4, `ITER = 0`). `budgets_offline.csv` is the same list with the
offline verdicts (single-core p = 1e-3 of Route 1 and Route 2 failed the offline stress test; they are still run here, the online run is the final test).
Route 3 is capped at 0.95 T = 95 ms (the uncapped high-water mark is above the admission limit), so it is admitted and validated.

Same set-up as `../../validation/` but with a single set of budgets (the empirical bound; no GEV set, so no estimator level in the folders):
14 budgets per scenario (Route 1 and Route 2 at p = 1e-1, 1e-2, 1e-3, Route 3 once, each without interference, with the memory enemy and with the cache enemy), 10000 jobs of 100 ms per instance
(16.7 min; about 4.5 h per scenario, both at the same time), multi-core on `rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`.
Only the budgets, the run ids (`rq2-val2-seg-*`) and the node folder (`/var/lib/rq2/results/seg_validation_p2`) differ, so nothing of the first validation is overwritten.

**Test power.** At p = 1e-3, 10000 jobs give about 10 expected overruns, which is little for the one-sided bound of the notebook. For a sharper test at p = 1e-3
raise `JOBS` in `make_manifests.py` (20000 jobs = 33 min per run) and regenerate; the runner reads the job count from `runs.csv`.

```bash
python3 make_manifests.py                                     # budgets.csv -> pods/, runs.csv, step5_input/budgets.csv (already done)
DRY_RUN=1 ./run_validation.sh                                  # the plan, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &
./run_validation.sh --scenario single_core                     # or one scenario / --route route1|route2b|hwm
tail -f results/logs/single_core/validation.log
```
Results land in `results/<scenario>/<route>/<ptag>_<none|memory|cache>/instance*.csv`, which is where `analysis_workload2.ipynb` (sections 7 and 8, `ITER = 0`) reads them.
After a recalibration (section 8 writes `budgets_workload2_iter1.csv`): copy this folder to `../iter1/`, replace `budgets.csv`, regenerate, and validate on fresh runs.

## Interference
Three conditions per budget: no enemy, the memory enemy (2662400 KB buffer) and the cache enemy (266240 KB, the last-level cache), as in the profiling; the enemies run on the
node's other cores (`enemy_cpus` in `runs.csv`, buffer in `enemy_kb`). That makes 21 runs per scenario (about 6.6 h per scenario). To skip one condition, delete its rows from `runs.csv`
(or its pods) before starting; the notebook reads `INTERFERENCES` in its configuration cell.

**Decision (12 Oct):** the cache runs are not part of this round. `runs.csv` has only none and memory (28 runs per workload); the full plan with cache is in `runs_with_cache.csv`
and the cache pods are kept in `pods/`. To add them later: put the cache rows back into `runs.csv` and start `run_validation.sh` again (collected runs are skipped),
and add `"cache"` to `INTERFERENCES` in the notebook.
