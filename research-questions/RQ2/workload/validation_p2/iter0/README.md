# Online validation, procedure 2, iteration 0 (video workload)

The budgets of `budgets.csv` come from `analysis_procedure2/analysis_workload1.ipynb` (section 6.4, `ITER = 0`); `budgets_offline.csv` is the same list with the offline verdicts.
All 14 budgets per scenario are admitted (Q/T between 0.43 and 0.79; Route 3 is 33.0 ms single-core and 26.5 ms multi-core).

Same set-up as `../../../workload2/validation_p2/iter0/` and the audio one: Route 1 and Route 2 at p = 1e-1, 1e-2, 1e-3 plus Route 3 once, each without interference and with the memory enemy
(2662400 KB buffer, on the node's other cores): 14 runs per scenario, 28 pods. The workload is the one of the profiling (`../../pods/single_core_pod.yaml`, `../../configs/multi_core.json`, image
`pippina2/rq2-workload:v2`, work 5); only jobs (20000 = 13.9 min at the 41.667 ms period, about 3.5 h per scenario, both scenarios at the same time), output and budget change.
Multi-core on `rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`. Run ids `rq2-val2-vid-*`, node folder `/var/lib/rq2/results/video_validation_p2`, so nothing of the first validation (`../../../validation/`) is overwritten.
No cache runs in this round.

**Test power.** At p = 1e-3, 20000 jobs give about 20 expected overruns; the old validation used 50000 (set `JOBS` in `make_manifests.py` and regenerate; the runner reads the job count from `runs.csv`).

```bash
python3 make_manifests.py                                     # budgets.csv -> pods/, runs.csv, step5_input/budgets.csv (already done)
DRY_RUN=1 ./run_validation.sh                                  # the plan, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &
./run_validation.sh --scenario single_core                     # or one scenario / --route route1|route2b|hwm
tail -f results/logs/single_core/validation.log
```
Results land in `results/<scenario>/<route>/<ptag>_<none|memory>/instance*.csv`. In `analysis_workload1.ipynb` set
`VALID_RESULTS = ROOT / "workload" / "validation_p2" / f"iter{ITER}" / "results"` in the configuration cell (its `ROOT` is `..`).
After a recalibration (section 8 writes `budgets_workload1_iter1.csv`): copy this folder to `../iter1/`, replace `budgets.csv`, regenerate, and validate on fresh runs.
