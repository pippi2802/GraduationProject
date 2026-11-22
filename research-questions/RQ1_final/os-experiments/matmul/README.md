# matmul workload: same experiment as os-experiments, kernel replaced

This folder is a copy of `os-experiments` (same `apply.sh`, `run_job.sh`, `run_config.sh`, `calibrate.py`, `generate_yaml.py`, `use_full_isolation_k.sh`,
`models/*.sh`, same workload names `model1`, `model5-phys`, `01-model1` to `08-model5`) with ONE change: the sieve is replaced by a **matrix multiplication**.
Setup and execution are the same as for the sieve runs; only these differ:
- kernel (`workload.c`): three N x N double matrices, initialised once, plain i-k-j loop, `-O2`, no BLAS/OpenMP; one `--K` = one full multiplication (K = n_iter);
  `matrix_M` in the CSV = N. Image `pippina2/rq1final-matmul:v1` (`./build.sh`).
- cores: single-core task on **cpu 2** (as before), multi-core claim over **cpus 1 and 2** (`requestedCpus [1,2]`, was `[1,3]`).
- namespace, node label and host path of every workload are prefixed `mm-` (`mm-m1`, `mm-01-model1`, ...) so nothing collides with the sieve runs on the nodes.
- results go to `test-results/results/<workload>_round<N>/` of THIS folder.

## Matrix size
N = 256 is 1.5 MiB, inside a 2 MiB private L2 (check on the workers: `cat /sys/devices/system/cpu/cpu2/cache/index*/size`; an AMD EPYC worker has only 512 KiB).
One 256 x 256 multiplication takes tens of ms, longer than the 10 ms tight period, so like the sieve bound the size is scale-dependent:
**soft (P = 100 ms) N = 256, tight (P = 10 ms) N = 64** (`make_workloads.py`; change with `MM_N_SOFT`, `MM_N_TIGHT`, then rerun it). n_iter is an integer: at about 30 ms per
multiplication soft cells land on 30, 60, 90 ms medians, and U = 0.1 (target 7 ms) cannot be reached. `calibrate.py` records this (`off_target`, `effective_u`).
Optional, to look at the cost per N before calibrating: `python3 probe_cost.py --rt-cpu 2` (needs the node labelled for `mm-m1`, see Calibration).

## Calibration (once, on a VM in full isolation, frequency pinned) = the same one-table design as `use_full_isolation_k.sh`
```
cd ~/GraduationProject/research-questions/RQ1_final/os-experiments/matmul
kubectl label node <full-isolation node> experiment-model=mm-m1 --overwrite     # calibrate.py starts its pod on this label
python3 calibrate.py model1 --rt-cpu 2
kubectl label node <full-isolation node> experiment-model=mm-m5-phys --overwrite
python3 calibrate.py model5-phys --rt-cpu 2
./use_full_isolation_k.sh            # copies the two tables to 01..08 and generates all manifests
```

## Per VM (same as for the sieve runs)
`<cfg>` = full | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 (full isolation, then one lever removed; 07 all defaults).
1. Node state: as for the sieve: baseline `kubedeadline-experiments/node-prep` (`setup-all.sh`), then the scenario script `models/<NN>_*.sh <ns> apply`
   (`<ns>` = namespace of the agent on that node, e.g. `mm-01-model1`): 01_isolcpus_only, 02_nohz_full_only, 03_rcu_nocbs_only, 04_systemd_contain, 05_irq_steer,
   06_boot_params, 07_worst_case, 08_freq_unpinned; `full` = the baseline alone. A VM that carries other settings: run `models/07_worst_case.sh <ns> apply` first to strip them
   and check `systemctl show system.slice -p AllowedCPUs` is empty afterwards (a leftover `AllowedCPUs=0` in `/etc/systemd/system.control/system.slice.d` is containment still on).
2. Reboot the VM, then seed it (the seed is lost at each reboot):
```
A=$(kubectl -n <ns> get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}')
kubectl -n <ns> exec -i "$A" -- nsenter --target 1 --mount --pid -- bash -s < ~/GraduationProject/setup/scripts/rt-budget-seed.sh
models/verify_scenario.sh <ns> <scenario>      # full_isolation | isolcpus_only | nohz_full_only | rcu_nocbs_only | systemd_contain | irq_steer | boot_params | worst_case | freq_unpinned
```
3. Label the node and deploy the agent of the single-core model (agent checked):
```
kubectl label node <node> experiment-model=mm-<cfg>-model1 --overwrite      # full: mm-m1 and ./apply.sh model1
./apply.sh <cfg>-model1                                                       # 07 and 08: SKIP_FREQ_PIN=1 ./apply.sh <cfg>-model1
```
4. Run one round = single-core (all U), then multi-core (`run_config.sh` relabels and deploys the multi-core agent itself). The command, four times (rounds 1 to 4):
```
for r in 1 2 3 4; do ./run_config.sh <cfg> <node> $r; done > logs/driver_<cfg>.log 2>&1 &        # full: <cfg> = full
```
   Prefix `SKIP_FREQ_PIN=1` for 07 and 08. Without isolcpus (01 and 07) the RT cap is about 790003, so U = 0.94 is not admissible: prefix `U_MAX=0.7` for those two
   (as for the sieve 07 runs: `CV_THRESHOLD=0.06 U_MAX=0.7`). mkdir `logs` and `test-results` first if missing.
   Monitor: `grep -h "^\[run\] done" test-results/logs/run_*_round1.log`; `ls test-results/results`.

## VMs and waves
9 configurations: wave 1 (6 VMs, workers 0 to 5) = full, 01, 02, 03, 04, 05; wave 2 = 06, 07, 08 (reconfigure three VMs, reboot, seed again). About 80 min per round (4 U, both models),
about 5.5 h per configuration for 4 rounds.
