# Online validation, procedure 3 with its final budgets (validation_p4, audio workload)

Same plan as `../../validation_p3/iter0/` (two levels, relaxed and strict, eps = 1%), but with the budgets of the **final procedure** (`analysis_procedure3/analysis_workload3.ipynb`, section 5.5):
Q* = max(C_p, C_mk) x alpha_drift (x alpha_platform for Route 2), C_p and C_mk bounds of C + delta (delta = 20 us), C_mk by counting the windows of k jobs with more than floor((k-m)/2) overruns,
alpha_drift = the spread of C_p across the baselines (the spread of C_mk is reported, not used). `budgets.csv` is `budgets/budgets_workload3_p3_iter0.csv` of that notebook.

| scenario | route | level | p | (m,k) | C_p | C_mk | Q* (ms) | Q*/T | p3 Q* (ms) | change |
|---|---|---|---|---|---|---|---|---|---|---|
| multi_core | route1 | relaxed | 0.01 | (95,100) | 1.100 | 1.141 | 1.415 | 0.142 | 1.568 | -9.7% |
| multi_core | route1 | strict | 0.001 | (99,100) | 1.175 | 1.305 | 1.794 | 0.179 | 1.790 | +0.2% |
| multi_core | route2b | relaxed | 0.01 | (95,100) | 1.109 | 1.186 | 1.560 | 0.156 | 1.702 | -8.3% |
| multi_core | route2b | strict | 0.001 | (99,100) | 1.691 | 1.386 | 2.464 | 0.246 | 2.446 | +0.7% |
| single_core | route1 | relaxed | 0.01 | (95,100) | 1.089 | 1.192 | 1.218 | 0.122 | 1.281 | -4.9% |
| single_core | route1 | strict | 0.001 | (99,100) | 1.259 | 2.426 | 2.637 | 0.264 | 2.557 | +3.1% |
| single_core | route2b | relaxed | 0.01 | (95,100) | 1.083 | 1.165 | 1.321 | 0.132 | 1.390 | -5.0% |
| single_core | route2b | strict | 0.001 | (99,100) | 1.257 | 2.064 | 2.490 | 0.249 | 2.463 | +1.1% |

**Runs.** 16 runs: both levels, both routes, both deployments, with and without the memory enemy (about 1.4 h); 50000 jobs of 10 ms. Multi-core on `rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`, run ids `rq2-val4-*`, node folder `/var/lib/rq2/results/audio_validation_p4`, so nothing of the earlier validations is overwritten.
The three workloads share the nodes: run them one after the other (`../../../run_validation_p4_all.sh`).

```bash
DRY_RUN=1 ./run_validation.sh                                  # the plan, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &
```
Results land in `results/<scenario>/<route>/<level>_<none|memory>/instance*.csv`. Evaluation: `analysis_workload3.ipynb` section 7 with `ONLINE_DIR` pointing here, or `p3_results_table.py`.
