# Online validation, procedure 2, iteration 1 (audio workload)

`budgets.csv` = the recalibrated budgets (`analysis_procedure2/analysis_workload3.ipynb` section 8, `Q1 = max(Q0, alpha_drift * C_val)`, then the monotone rule in p) computed from the
iteration-0 runs in `../iter0/results`. Seven budgets changed (+5% to +34%); only those are validated again, without interference and with the memory enemy (14 runs; about 1.2 h).
The budgets that did not change keep their iteration-0 result. `runs_all.csv` is the full plan (all 42 including cache).

Fresh runs only: new run ids (`rq2-val2i1-aud-*`) and node folder (`/var/lib/rq2/results/audio_validation_p2_i1`), so nothing of iteration 0 is reused.

```bash
DRY_RUN=1 ./run_validation.sh
nohup ./run_validation.sh > run_validation.out 2>&1 &
```
Then in the notebook: `ITER = 1` (reads `../iter1/results`, budgets of `budgets_workload3_iter1.csv` / this `budgets.csv`).
This is the last recalibration allowed by `K_MAX = 2` before the fallback to Route 3 would apply to a cell that still fails.
