# Online validation, procedure 3, iteration 0 (audio workload)

Two levels, both with eps = 1% of violating windows (k = 100 audio blocks = 1 s):
- **relaxed:** p = 1e-2 and a window requirement that tolerates a single overrun (two or more misses allowed per window),
- **strict:** p = 1e-3 and a window requirement that allows one miss per window, i.e. effectively no overrun.

Each budget is Q* = max(Q_p, Q_(m,k)) of `analysis_procedure3/analysis_workload3.ipynb` (sections 5.4 and 5.5; `budgets.csv` is `budgets/budgets_workload3_p3_iter0.csv` of that notebook).
(m,k) means at least m of any k consecutive jobs meet their deadline. Q_(m,k) comes from the reservation model of section 5.4 (CBS, 20 us per job, dispatch wait W of the profiling runs);
the extra budget the window requirement costs is `extra over Q_p`. The routes are the ones of procedure 2 (Route 1: stress profiling, Route 2: baseline profiling with the platform factor); Route 3 has no window effect and is not run.

| scenario | route | level | p | (m,k) | Q_p (ms) | Q_(m,k) (ms) | Q* (ms) | Q*/T | extra over Q_p | dominates |
|---|---|---|---|---|---|---|---|---|---|---|
| multi_core | route1 | relaxed | 0.01 | (95,100) | 1.345 | 1.568 | 1.568 | 0.157 | +16.6% | (m,k) |
| multi_core | route1 | strict | 0.001 | (99,100) | 1.594 | 1.790 | 1.790 | 0.179 | +12.2% | (m,k) |
| multi_core | route2b | relaxed | 0.01 | (95,100) | 1.437 | 1.702 | 1.702 | 0.170 | +18.4% | (m,k) |
| multi_core | route2b | strict | 0.001 | (99,100) | 2.446 | 2.029 | 2.446 | 0.245 | +0.0% | p |
| single_core | route1 | relaxed | 0.01 | (95,100) | 1.092 | 1.281 | 1.281 | 0.128 | +17.3% | (m,k) |
| single_core | route1 | strict | 0.001 | (99,100) | 1.349 | 2.557 | 2.557 | 0.256 | +89.6% | (m,k) |
| single_core | route2b | relaxed | 0.01 | (95,100) | 1.206 | 1.390 | 1.390 | 0.139 | +15.3% | (m,k) |
| single_core | route2b | strict | 0.001 | (99,100) | 1.495 | 2.463 | 2.463 | 0.246 | +64.8% | (m,k) |

**Runs.** 16 runs: both levels, both routes, both deployments, with and without the memory enemy (about 1.4 h, both deployments at the same time); 50000 jobs of 10 ms (8.3 min per run). Multi-core on `rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`, run ids `rq2-val3-*`, node folder `/var/lib/rq2/results/audio_validation_p3`, so nothing of the earlier validations is overwritten.

**Test power.** At p = 1e-3 the rate test is close to its confidence limit with this run length (N*p = 50): some strict cells may come out inconclusive. That is a property of the run length, not of the procedure.

```bash
python3 make_manifests.py                                     # budgets.csv -> pods/, runs.csv (already done)
DRY_RUN=1 ./run_validation.sh                                  # the plan, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &
```
All three workloads one after the other (they share the nodes): `../../../run_validation_p3_all.sh`.
Results land in `results/<scenario>/<route>/<level>_<none|memory>/instance*.csv` (progress: `results/*/validation.log` or `results/logs/*/validation.log`, as the runner of this workload writes it).
