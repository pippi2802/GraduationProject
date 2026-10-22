# Online validation, procedure 3 with its final budgets (validation_p4, segmentation workload)

Same plan as `../../validation_p3/iter0/` (two levels, relaxed and strict, eps = 1%), but with the budgets of the **final procedure** (`analysis_procedure3/analysis_workload2.ipynb`, section 5.5):
Q* = max(C_p, C_mk) x alpha_drift (x alpha_platform for Route 2), C_p and C_mk bounds of C + delta (delta = 20 us), C_mk by counting the windows of k jobs with more than floor((k-m)/2) overruns,
alpha_drift = the spread of C_p across the baselines (the spread of C_mk is reported, not used). `budgets.csv` is `budgets/budgets_workload2_p3_iter0.csv` of that notebook.

| scenario | route | level | p | (m,k) | C_p | C_mk | Q* (ms) | Q*/T | p3 Q* (ms) | change |
|---|---|---|---|---|---|---|---|---|---|---|
| multi_core | route1 | relaxed | 0.01 | (8,10) | 58.980 | 59.129 | 70.266 | 0.703 | 70.361 | -0.1% |
| multi_core | route1 | strict | 0.001 | (9,10) | 60.499 | 59.851 | 71.893 | 0.719 | 71.874 | +0.0% |
| multi_core | route2b | relaxed | 0.01 | (8,10) | 56.184 | 56.185 | 70.773 | 0.708 | 70.869 | -0.1% |
| multi_core | route2b | strict | 0.001 | (9,10) | 57.122 | 56.832 | 71.953 | 0.720 | 71.933 | +0.0% |
| single_core | route1 | relaxed | 0.01 | (8,10) | 53.432 | 53.471 | 62.938 | 0.629 | 63.127 | -0.3% |
| single_core | route1 | strict | 0.001 | (9,10) | 54.848 | 54.621 | 58.853 | 0.589 | 64.580 | -8.9% |
| single_core | route2b | relaxed | 0.01 | (8,10) | 50.482 | 50.536 | 66.026 | 0.660 | 66.322 | -0.4% |
| single_core | route2b | strict | 0.001 | (9,10) | 51.356 | 51.027 | 61.168 | 0.612 | 66.966 | -8.7% |

**Runs.** 4 runs: both levels, both routes, single-core only, memory enemy only (about 2.4 h); 20000 jobs of 100 ms. Multi-core on `rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`, run ids `rq2-val4-*`, node folder `/var/lib/rq2/results/seg_validation_p4`, so nothing of the earlier validations is overwritten.
The three workloads share the nodes: run them one after the other (`../../../run_validation_p4_all.sh`).

```bash
DRY_RUN=1 ./run_validation.sh                                  # the plan, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &
```
Results land in `results/<scenario>/<route>/<level>_<none|memory>/instance*.csv`. Evaluation: `analysis_workload2.ipynb` section 7 with `ONLINE_DIR` pointing here, or `p3_results_table.py`.
