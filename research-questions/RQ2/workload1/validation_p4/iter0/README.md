# Online validation, procedure 3 with its final budgets (validation_p4, video workload)

Same plan as `../../validation_p3/iter0/` (two levels, relaxed and strict, eps = 1%), but with the budgets of the **final procedure** (`analysis_procedure3/analysis_workload1.ipynb`, section 5.5):
Q* = max(C_p, C_mk) x alpha_drift (x alpha_platform for Route 2), C_p and C_mk bounds of C + delta (delta = 20 us), C_mk by counting the windows of k jobs with more than floor((k-m)/2) overruns,
alpha_drift = the spread of C_p across the baselines (the spread of C_mk is reported, not used). `budgets.csv` is `budgets/budgets_workload1_p3_iter0.csv` of that notebook.

| scenario | route | level | p | (m,k) | C_p | C_mk | Q* (ms) | Q*/T | p3 Q* (ms) | change |
|---|---|---|---|---|---|---|---|---|---|---|
| multi_core | route1 | relaxed | 0.01 | (22,24) | 22.283 | 22.588 | 23.250 | 0.558 | 23.296 | -0.2% |
| multi_core | route1 | strict | 0.001 | (23,24) | 22.736 | 22.828 | 23.443 | 0.563 | 23.710 | -1.1% |
| multi_core | route2b | relaxed | 0.01 | (22,24) | 22.123 | 22.428 | 24.470 | 0.587 | 24.553 | -0.3% |
| multi_core | route2b | strict | 0.001 | (23,24) | 22.535 | 22.641 | 24.647 | 0.592 | 24.927 | -1.1% |
| single_core | route1 | relaxed | 0.01 | (22,24) | 22.953 | 23.382 | 24.120 | 0.579 | 23.345 | +3.3% |
| single_core | route1 | strict | 0.001 | (23,24) | 23.527 | 23.613 | 24.131 | 0.579 | 23.808 | +1.4% |
| single_core | route2b | relaxed | 0.01 | (22,24) | 22.532 | 22.853 | 26.167 | 0.628 | 25.350 | +3.2% |
| single_core | route2b | strict | 0.001 | (23,24) | 22.961 | 23.056 | 26.154 | 0.628 | 25.766 | +1.5% |

**Runs.** 8 runs: both levels, both routes, both deployments, memory enemy only (about 1.6 h); 30000 jobs of 41.667 ms. Multi-core on `rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`, run ids `rq2-val4-*`, node folder `/var/lib/rq2/results/video_validation_p4`, so nothing of the earlier validations is overwritten.
The three workloads share the nodes: run them one after the other (`../../../run_validation_p4_all.sh`).

```bash
DRY_RUN=1 ./run_validation.sh                                  # the plan, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &
```
Results land in `results/<scenario>/<route>/<level>_<none|memory>/instance*.csv`. Evaluation: `analysis_workload1.ipynb` section 7 with `ONLINE_DIR` pointing here, or `p3_results_table.py`.
