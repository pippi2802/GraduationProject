# The RQ2 procedure: from a periodic workload to CBS budgets

Five steps, one folder each. Steps 1-3 collect data (on the VM or through kubectl), step 4 derives the budgets from the data of steps 1-3
without being told any path, step 5 validates the budgets online. Every step saves its results in its own `results/` folder.

| Step | What | Where it runs | Command | Result used by |
|---|---|---|---|---|
| 1 `step1_platform` | platform factors alpha_platform(m) from victim runs; optional noise floor | on the VM, once per VM type | `./run_platform.sh --victim-cpu 1 --enemy-cpus "2;2,3;2,3,0"` | step 4 |
| 2 `step2_profiling` | baseline1, cache, memory, baseline2 of YOUR workload | control plane (kubectl) | `./run_profiling.sh --scenario ... --pod-yaml ...` | step 4 |
| 3 `step3_drift_runs` | more baselines and one stressed run, other VM or other time | control plane (kubectl) | `./run_extra.sh baseline\|stress ...` | step 4 |
| 4 `step4_parameter_derivation` | bounds C_p, inflation factors, the budgets of Route 1, Route 2b and HWM, offline validation | anywhere with Python | `python3 main.py` | step 5 |
| 5 `step5_online_validation` | run the budgets on the cluster and check them | control plane + Python | `python3 validate.py matrix` / `check` | |

A new workload only needs its pod YAML (the contract is in `step2_profiling/README.md`); steps 1 and 4 do not know the workload at all.
Scenario names are yours (the examples use `single_core` and `multi_core`): the name you give in step 2 is the folder step 4 looks for.

Python needs numpy, pandas, scipy and matplotlib (step 5: numpy, pandas, scipy).
