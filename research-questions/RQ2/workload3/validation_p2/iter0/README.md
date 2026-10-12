# Online validation, procedure 2, iteration 0 (audio workload)

The budgets of `budgets.csv` come from `analysis_procedure2/analysis_workload3.ipynb` (section 6.4, `ITER = 0`). `budgets_offline.csv` is the same list with the
offline verdicts (which cells failed an offline test, still run here because the online run is the final test).

Same set-up as `../../validation/` (14 runs per scenario: Route 1 and Route 2b at p = 1e-1, 1e-2, 1e-3, Route 3 once, each without and with the memory enemy;
50000 jobs of 10 ms per instance; multi-core on `rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`, both scenarios at the same time as in the profiling).
Only the budgets, the run ids (`rq2-val2-aud-*`) and the node folder (`/var/lib/rq2/results/audio_validation_p2`) differ, so nothing of the first validation is overwritten.

```bash
python3 make_manifests.py                                     # budgets.csv -> pods/, runs.csv, step5_input/budgets.csv (already done)
DRY_RUN=1 ./run_validation.sh                                  # the plan, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &         # about 2.3 h
./run_validation.sh --scenario single_core                     # or one scenario / --route route1|route2b|hwm
tail -f results/single_core/validation.log
```
Results land in `results/<scenario>/<route>/<ptag>_<none|memory>/instance*.csv`, which is where `analysis_workload3.ipynb` (sections 7 and 8, `ITER = 0`) reads them.
To change a budget: edit `budgets.csv`, run `make_manifests.py` again.
After a recalibration (section 8 writes `budgets_workload3_iter1.csv`): copy this folder to `../iter1/`, replace `budgets.csv`, regenerate, and validate on fresh runs.
