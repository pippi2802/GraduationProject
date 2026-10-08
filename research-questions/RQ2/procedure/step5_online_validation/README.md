# Step 5: online validation

```bash
python3 validate.py matrix      # what to run: runtime and period to reserve for every run, and the folder to save the results in
python3 validate.py check       # the validation of the results you saved
```
1. `matrix` reads `../step4_parameter_derivation/results/budgets.csv` and prints (and saves in `report/run_matrix.csv`) one line per run: the reservation `runtime_us` of `period_us`,
   and `save_results_in`. Run your workload under that reservation, once without interference and once with the memory enemy, with a few tens of thousands of jobs.
2. Save every run's CSVs in `results/<scenario>/<route>/<p>_<interference>/` as `instance0.csv`, `instance1.csv`, ...  (route: `route1`, `route2b`, `hwm`; p: `p1e-1`, `p1e-2`, `p1e-3`;
   interference: `none` or `memory`; the HWM route has one budget for every p: `hwm/all_none`, `hwm/all_memory`). The CSVs need `cpu_ns`, `response_ns`, `skipped`, `warmup`.
3. `check` analyses every run it finds and writes one table, `report/online_validation.csv`: one row per scenario, route and p, and per interference condition
   - `P(C <= B*)`: share of the executed jobs whose execution time is within the reserved budget B* (worst instance). The tolerance p is the admissible
     probability that C exceeds the budget, so the budget is valid when `P(C <= B*) >= 1 - p`.
   - `over-budget %`: B* / B_oracle - 1, with B_oracle the (1 - p) quantile of C in that same run (the smallest budget that would have met p there).
   - `deadline miss (R > T)`: share of the jobs with response time above the period, or skipped (worst instance). Reported, not judged: with a hard
     reservation of period T an overrun implies a miss, but misses also come from the platform and the reservation mechanism (stalls, late starts,
     scheduler overheads), which are not part of C.
   Warm-up jobs are left out.
Folders that are not there are skipped and counted, so `check` can be run while the validation is still going.
