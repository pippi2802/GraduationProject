# Online validation, procedure 3, iteration 0 (segmentation workload)

Two levels, both with eps = 1% of violating windows (k = 10 images = 1 s):
- **relaxed:** p = 1e-2 and a window requirement that tolerates a single overrun (two or more misses allowed per window),
- **strict:** p = 1e-3 and a window requirement that allows one miss per window, i.e. effectively no overrun.

Each budget is Q* = max(Q_p, Q_(m,k)) of `analysis_procedure3/analysis_workload2.ipynb` (sections 5.4 and 5.5; `budgets.csv` is `budgets/budgets_workload2_p3_iter0.csv` of that notebook).
(m,k) means at least m of any k consecutive jobs meet their deadline. Q_(m,k) comes from the reservation model of section 5.4 (CBS, 20 us per job, dispatch wait W of the profiling runs);
the extra budget the window requirement costs is `extra over Q_p`. The routes are the ones of procedure 2 (Route 1: stress profiling, Route 2: baseline profiling with the platform factor); Route 3 has no window effect and is not run.

| scenario | route | level | p | (m,k) | Q_p (ms) | Q_(m,k) (ms) | Q* (ms) | Q*/T | extra over Q_p | dominates |
|---|---|---|---|---|---|---|---|---|---|---|
| multi_core | route1 | relaxed | 0.01 | (8,10) | 70.071 | 70.361 | 70.361 | 0.704 | +0.4% | (m,k) |
| multi_core | route1 | strict | 0.001 | (9,10) | 71.874 | 71.221 | 71.874 | 0.719 | +0.0% | p |
| multi_core | route2b | relaxed | 0.01 | (8,10) | 70.752 | 70.869 | 70.869 | 0.709 | +0.2% | (m,k) |
| multi_core | route2b | strict | 0.001 | (9,10) | 71.933 | 71.637 | 71.933 | 0.719 | +0.0% | p |
| single_core | route1 | relaxed | 0.01 | (8,10) | 62.873 | 63.127 | 63.127 | 0.631 | +0.4% | (m,k) |
| single_core | route1 | strict | 0.001 | (9,10) | 62.873 | 64.580 | 64.580 | 0.646 | +2.7% | (m,k) |
| single_core | route2b | relaxed | 0.01 | (8,10) | 65.934 | 66.322 | 66.322 | 0.663 | +0.6% | (m,k) |
| single_core | route2b | strict | 0.001 | (9,10) | 65.934 | 66.966 | 66.966 | 0.670 | +1.6% | (m,k) |

**Runs.** 4 runs: both levels, both routes, single-core only, memory enemy only (about 2.4 h); 20000 jobs of 100 ms (33.3 min per run). Multi-core on `rt-k8s-worker-6`, single-core on `rt-k8s-worker-7`, run ids `rq2-val3-*`, node folder `/var/lib/rq2/results/seg_validation_p3`, so nothing of the earlier validations is overwritten.

**Test power.** At p = 1e-3 the rate test is close to its confidence limit with this run length (N*p = 20): some strict cells may come out inconclusive. That is a property of the run length, not of the procedure.

```bash
python3 make_manifests.py                                     # budgets.csv -> pods/, runs.csv (already done)
DRY_RUN=1 ./run_validation.sh                                  # the plan, touches nothing
nohup ./run_validation.sh > run_validation.out 2>&1 &
```
All three workloads one after the other (they share the nodes): `../../../run_validation_p3_all.sh`.
Results land in `results/<scenario>/<route>/<level>_<none|memory>/instance*.csv` (progress: `results/*/validation.log` or `results/logs/*/validation.log`, as the runner of this workload writes it).
