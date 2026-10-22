# Workload 4: LiDAR point-cloud preprocessing (20 Hz, T = 50 ms)

A fourth workload to test the procedure on a **memory-bound task with irregular memory access** and a new period. Each job takes one Velodyne scan (KITTI, about 120 000 points),
copies it into an Open3D point cloud, runs **voxel downsampling** (0.5 m) and **ground-plane removal** (RANSAC plane, 100 iterations, 0.2 m threshold, inliers dropped).
It runs on one thread in a SCHED_FIFO task (priority 50), one scan at a time, with the same task model as the other workloads (absolute releases, skip on overrun, `cpu_ns` = thread CPU time of the job).
The scan content changes the cost of a job (point density, number of voxels, RANSAC inliers), as the pictures do for workload 2.

## Files
- `run.py`: the task (same CSV columns and flags as `workload2/run.py`, `OMP_NUM_THREADS=1`, fixed Open3D seed). `configs/{single,multi}_core.json`: cpus, FIFO priority, algorithm parameters.
- `prepare_scans.py`: copies KITTI scans into `scans/`.
- `Dockerfile`: `pippina2/rq2-lidar:v1` (python 3.12-slim + open3d; needs `libgomp1 libegl1 libgl1 libusb-1.0-0 libidn2-0`, found by running it).
- `pods/{single,multi}_core_pod.yaml`: generous reservation for profiling (46500 of 50000 us); step 3 passes `--jobs`.
- `run_experiments.sh`: the profiling and drift campaign.
- `validation_p4/iter0/`: the online validation with the final budgets (`make_manifests.py`, `run_validation.sh`); needs the `budgets.csv` of the notebook.
- `../analysis_procedure3/analysis_workload4.ipynb`: the procedure (budgets, offline validation, online validation); levels relaxed (p = 1e-2, (18,20)) and strict (p = 1e-3, (19,20)), k = 1 s = 20 scans.

## 1. Data and image (once)
KITTI raw data (CC BY-NC-SA 3.0, do not redistribute): download "synced+rectified data" of a few city drives, e.g. 2011_09_26_drive_0001, 0005, 0011, 0013 (662 frames, 2.5 GB): only the "synced+rectified data" zip of each, and only its LiDAR part: `unzip -q <zip> "*velodyne_points/*"` into one folder.
```bash
python3 prepare_scans.py ../data                 # all the scans found; --n N keeps the first N
docker build -t pippina2/rq2-lidar:v1 . && docker push pippina2/rq2-lidar:v1
```

## 2. Calibrate before the campaign (on a worker, 5 minutes)
The cost of a job depends on the machine and on the parameters, so **look at C before profiling**: the reservation of the pods (93% of T = 46.5 ms) must stay far above C, and the task should be loaded but not near T.
```bash
python3 run.py configs/single_core.json jobs=300 period_ms=0 output='"/tmp/lidar"'      # continuous flow, on the worker with the image's python
```
Look at the printed `cpu_ms median / p99 / max`. Aim at a median of 15-30 ms (30-60% of T, like the video and segmentation workloads). Too high or too low: change `voxel_m` (0.3-0.7; a larger voxel is faster) or `plane_iters` in the two configs, rebuild, push.
**Do not change them afterwards**: profiling, drift and validation must use the same task. (On a laptop, one unpinned core, the real KITTI scans take about 27 ms at 0.5 m / 100 iterations (62 ms at 0.3 m / 200): the Xeon 8573C of the workers is expected to be faster, but this is not measured.)

## 3. Profiling and drift (the generic procedure scripts)
```bash
DRY_RUN=1 workload4/run_experiments.sh profile                                           # the plan
nohup workload4/run_experiments.sh profile > workload4/results/profile.out 2>&1 &         # baseline1, cache, memory, baseline2 of both scenarios, 50000 jobs per run, about 3 h
nohup workload4/run_experiments.sh swap    > workload4/results/swap.out 2>&1 &            # one baseline, one memory-stressed and one cache-stressed run on the other nodes, 30000 jobs, about 1.5 h; AFTER profile, never together
```
Enemies, cores and m are those of the other workloads (single-core: cpu1, enemies on 2,3,0, m = 3; multi-core: cpu1+cpu2, enemies on 3,0, m = 2; memory enemy 2 662 400 KB, cache enemy 266 240 KB = the 260 MiB L3 of the VM).
The three other workloads use the same nodes: run this one when no other campaign is running (`check_overlap.py` in RQ2 tells afterwards whether two runs overlapped).
Then copy the results as for workload 2: `procedure/step2_profiling/results/lidar_{single,multi}/<run>` to `workload4/results/{single,multi}_core/<run>`, and `procedure/step3_drift_runs/results/lidar_*/extra_baselines/swap` and `stress_run` to `workload4/alpha_drift/results/<worker7 for single, worker6 for multi>/<scenario>/{baseline,memory}`, and `results/lidar_*_cache/stress_run` to `.../<scenario>/cache`.
A second drift VM (as `worker0` for the video) is optional; the notebook reads `worker6` and `worker7`.

## 4. Budgets and validation
1. `analysis_procedure3/analysis_workload4.ipynb`: run it (section 5.5 writes `budgets/budgets_workload4_p3_iter0.csv`).
2. Copy that file to `validation_p4/iter0/budgets.csv`, then `python3 make_manifests.py` there (writes `pods/` and `runs.csv`; 40 000 jobs of 50 ms = 33 min per run, memory enemy, the three variants, both levels, both scenarios: 8 runs, about 2.8 h with the two scenarios at the same time).
3. `DRY_RUN=1 ./run_validation.sh`, then `nohup ./run_validation.sh > run_validation.out 2>&1 &` (or `ONLY=workload4 ../../../run_validation_p4_all.sh`). Tables: `python3 ../../../p4_results_table.py`.
   The notebook's section 7 reads the same folder (`VALID_DIR` = `workload4/validation_p4`); a recalibration (section 8) is a new `iter1`.

## Not tested here
Only `run.py` and the image were run, on a laptop with synthetic scans (`cpu_ns` matched the wall time, so the job is single-threaded), and `make_manifests.py` with a stand-in budgets file. Nothing ran on the cluster, no KITTI scans were available, the pods were not applied, and `run_experiments.sh` was only dry-run. The notebook is a copy of workload 2's with a new configuration entry; it was not executed for workload 4 (no data).
