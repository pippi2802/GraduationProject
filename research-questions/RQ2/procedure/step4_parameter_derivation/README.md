# Step 4: parameter derivation

```bash
python3 main.py                                   # every scenario found in ../step2_profiling/results
python3 main.py --scenarios single_core --m single_core=3
```
No path is needed: it reads `../step1_platform/results/{platform_factor,noise_floor_summary}.csv`, `../step2_profiling/results/<scenario>/` and
`../step3_drift_runs/results/<scenario>/`. The enemy cores m come from step 2's `profiling.json` (override: `--m scenario=m`), the pairing of the stressed run from
step 3's `paired_with.txt` (override: `--stress-baseline scenario=label`), the period T from the `release_ns` column (override: `--period-ms`).
Explicit factors instead of step 1's table: `--platform-factors 1=1.03 2=1.06 3=1.11`. Defaults can also be edited at the top of `main.py`; the tolerances and
the method constants are in `config.py`.

## What it prints (every table is also saved as CSV in `results/`, every figure as PNG)
1. **data usable?** `data_summary` (jobs, skipped, late, C per run), `p_floor` (stalls no budget removes), `platform_events_*` (multi-instance, frames that repeat), `noise_floor`
2. **bounds**: `bounds` (C_p per run and tolerance, GEV bound, theta, xi, Gumbel test), figure `evt_fit_<scenario>.png` (pdf, QQ, return level)
3. **inflation factors**: `inflation_factors` (alpha_drift, alpha_cores, alpha_platform), `platform_factor`, `alpha_cores_profiling`, `alpha_cores_stress_run`
4. **budgets**: `budgets_summary` (Q in ms and Q/T per route and tolerance; HWM is one budget for every p), **`budgets.csv`** (the file step 5 reads: scenario, route, p, Q_ms, runtime_us, period_us ...), `budgets_per_instance.csv`, `budgets_other_tolerances_*.csv`, figure `risk_curve_<scenario>.png`
5. **offline validation**: `bound_check` (C_p of baseline1 on baseline2), `held_out_replay`, `burst_check`, `leave_one_out`, `stress_run_check`
6. **`validity_summary`**: every check as PASS / FAIL / info. FAIL needs attention (for example fewer than 3 baseline runs, a budget that does not cover the stressed run); info lines are for your judgement.

## The routes
Route 1: Q = C_p of the stress runs x alpha_drift. Route 2b: Q = C_p of the baselines x alpha_platform(m) x alpha_drift. HWM: the largest C of the stress runs x alpha_drift / 0.96, one budget for every p.
Multi-instance scenarios have one reservation: the budget is the maximum over the instances.

## The code
`config.py` (Config, ScenarioInput) - `data.py` (Run, Scenario) - `EVT.py` (TailEstimator, BoundEstimator, EVT) - `inflationFactors.py` (AlphaDrift, AlphaCores, PlatformFactor, InflationFactors) -
`parameterDerivation.py` (Route1, Route2b, HighWaterMark, ParameterDerivation) - `offlineValidation.py` (Replay, HeldOutReplay, BurstCheck, BoundCheck, LeaveOneOut, StressRunCheck) -
`dataValidity.py` (DataSummary, PFloor, PlatformEvents, NoiseFloorCheck) - `riskCurve.py` (RiskCurve) - `report.py` (Report) - `procedure.py` (Procedure, Results).
From Python: `Procedure(cfg).run()` returns a `Results` with the budgets, factors, bounds and the validity summary.
