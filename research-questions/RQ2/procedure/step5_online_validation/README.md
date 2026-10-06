# Step 5: online validation

```bash
python3 validate.py matrix      # what to run: runtime and period to reserve for every run, and the folder to save the results in
python3 validate.py check       # the validation of the results you saved
```
1. `matrix` reads `../step4_parameter_derivation/results/budgets.csv` and prints (and saves in `report/run_matrix.csv`) one line per run: the reservation `runtime_us` of `period_us`,
   and `save_results_in`. Run your workload under that reservation, once without interference and once with the memory enemy, with a few tens of thousands of jobs.
2. Save every run's CSVs in `results/<scenario>/<route>/<p>_<interference>/` as `instance0.csv`, `instance1.csv`, ...  (route: `route1`, `route2b`, `hwm`; p: `p1e-1`, `p1e-2`, `p1e-3`;
   interference: `none` or `memory`; the HWM route has one budget for every p: `hwm/all_none`, `hwm/all_memory`). The CSVs need `skipped`, `deadline_met`, `cpu_ns`.
3. `check` analyses every run it finds and writes `report/`:
   - `online_verdicts`: budget-miss rate / p and PASS / pass? / FAIL per route and tolerance, without and with the memory enemy. The pass rule is in the header of `validate.py`
     (a miss event with a job above Q* is a budget miss; any other is a platform stall and is not counted; pass? = the point estimate is within p but the 95% bound is not).
   - `scheduler_assumption`: late jobs by how much of Q* they need. ~0% below the margin and ~100% above Q* confirms the model "late only when C > Q*".
   - `platform_stalls`: the stalls against the profiling bound of p_floor. Clearly above it points at the scheduler or the reservation, not the platform.
   - `online_vs_offline`: the memory runs against step 4's burst check at the same budget. `over_budgeting`: how much more than needed was reserved.
   - `online_runs.csv`: every run with its counts.
Folders that are not there are skipped and counted, so `check` can be run while the validation is still going.
