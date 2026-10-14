# Online validation, procedure 3, iteration 0 (video workload)

Two levels, both with eps = 1% of violating windows (k = 24 frames = 1 s):
- **relaxed:** p = 1e-2 and a window requirement that tolerates a single overrun (two or more misses allowed per window),
- **strict:** p = 1e-3 and a window requirement that allows one miss per window, i.e. effectively no overrun.

Each budget is Q* = max(Q_p, Q_(m,k)) of `analysis_procedure3/analysis_workload1.ipynb` (sections 5.4 and 5.5; `budgets.csv` is `budgets/budgets_workload1_p3_iter0.csv` of that notebook).
(m,k) means at least m of any k consecutive jobs meet their deadline. Q_(m,k) comes from the reservation model of section 5.4 (CBS, 20 us per job, dispatch wait W of the profiling runs);
the extra budget the window requirement costs is `extra over Q_p`. The routes are the ones of procedure 2 (Route 1: stress profiling, Route 2: baseline profiling with the platform factor); Route 3 has no window effect and is not run.

| scenario | route | level | p | (m,k) | Q_p (ms) | Q_(m,k) (ms) | Q* (ms) | Q*/T | extra over Q_p | dominates |
|---|---|---|---|---|---|---|---|---|---|---|
| multi_core | route1 | relaxed | 0.01 | (22,24) | 22.916 | 23.296 | 23.296 | 0.559 | +1.7% | (m,k) |
| multi_core | route1 | strict | 0.001 | (23,24) | 23.329 | 23.710 | 23.710 | 0.569 | +1.6% | (m,k) |
| multi_core | route2b | relaxed | 0.01 | (22,24) | 24.117 | 24.553 | 24.553 | 0.589 | +1.8% | (m,k) |
| multi_core | route2b | strict | 0.001 | (23,24) | 24.510 | 24.927 | 24.927 | 0.598 | +1.7% | (m,k) |
| single_core | route1 | relaxed | 0.01 | (22,24) | 23.122 | 23.345 | 23.345 | 0.560 | +1.0% | (m,k) |
| single_core | route1 | strict | 0.001 | (23,24) | 23.599 | 23.808 | 23.808 | 0.571 | +0.9% | (m,k) |
| single_core | route2b | relaxed | 0.01 | (22,24) | 25.195 | 25.350 | 25.350 | 0.608 | +0.6% | (m,k) |
| single_core | route2b | strict | 0.001 | (23,24) | 25.565 | 25.766 | 25.766 | 0.618 | +0.8% | (m,k) |

**Runs.** 8 runs: both levels, both routes, both deployments, memory enemy only (about 1.6 h, both deployments at the same time); 30000 jobs of 41.667 ms (20.8 min per run). Multi-core on `rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`, run ids `rq2-val3-*`, node folder `/var/lib/rq2/results/video_validation_p3`, so nothing of the earlier validations is overwritten.

**Test power.** At p = 1e-3 the rate test is close to its confidence limit with this run length (N*p = 30): some strict cells may come out inconclusive. That is a property of the run length, not of the procedure.

```bash
python3 make_manifests.py                                     # budgets.csv -> pods/, runs.csv (already done)
DRY_RUN=1 ./run_validation.sh                                  # the plan, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &
```
All three workloads one after the other (they share the nodes): `../../../run_validation_p3_all.sh`.
Results land in `results/<scenario>/<route>/<level>_<none|memory>/instance*.csv` (progress: `results/*/validation.log` or `results/logs/*/validation.log`, as the runner of this workload writes it).
