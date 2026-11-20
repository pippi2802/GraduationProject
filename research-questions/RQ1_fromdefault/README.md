# RQ1_fromdefault: switch ONE lever on, starting from an all-defaults node

RQ1_final reverts one lever at a time from full isolation (subtractive). Here the direction is reversed (additive): start from the
all-defaults node (RQ1_final scenario 07) and switch on exactly one lever. Same workload, same calibration, same data, same metrics
(`os-experiments/results_final` and `tmp/pooled` in RQ1_final can be reused: S = p99.9/median, miss+skip rate, dM against the reference).
Nothing here modifies RQ1_final.

## Configurations (numbering of RQ1_final kept; d = "from default")
| code | switched on | how | reboot |
|---|---|---|---|
| d07 | nothing (all defaults, reference row) | `levers/defaults.sh` | yes |
| d01 | isolcpus | `levers/lever.sh <ns> isolcpus apply` | yes |
| d02 | nohz_full | `... nohz_full apply` | yes |
| d03 | rcu_nocbs | `... rcu_nocbs apply` | yes |
| d04 | systemd containment (system.slice/user.slice -> cpu0) | `... systemd apply` | no |
| d05 | IRQ steering (all IRQs -> cpu0) | `... irq_steer apply` | no |
| d06 | boot-params bundle (mitigations=off, THP never, rcu_nocb_poll) | `... boot_params apply` | yes |
| d08 | frequency pinning (performance, no turbo, min=max) | `... freq_pin apply` + agent without SKIP_FREQ_PIN | no |
Each exists as single-core (`dNN-model1`, one reserved cpu) and multi-core (`dNN-model5`, count=2 claim on cpus 1,3), 16 workloads in `workloads/`.
The tokens/units are the ones of `kubedeadline-experiments/node-prep/{isolate,harden}-core.sh` (full isolation), so "all levers on" = RQ1_final's baseline.
keep_cpu = 0 (housekeeping cpu), isolated set = all other cpus, as in the baseline.

## What is identical to RQ1_final
job.yaml (from the 07 workloads: same requestedCpus, same pod script, same `taskset -c $RT_CPUSET` for multi-core), workload.c, scales (tight P = 10 ms, soft P = 100 ms),
headroom 0.7, 5000 jobs per cell, and ONE K table for everything: the full-isolation calibration (model1 / model5-phys), as in `use_full_isolation_k.sh`.
Utilizations: 0.1, 0.5, 0.7, 0.94 (the four used in the analysis; edit `UTILS` in make_workloads.py and rerun it for all ten).
Difference: `run_job.sh` also collects `jobs_2.csv` (second process of the multi-core pod).
Regenerate: `python3 make_workloads.py && for d in workloads/d*; do python3 generate_yaml.py $(basename $d); done`.

## Procedure per VM (the 5 new VMs)
0. Once per VM: join the cluster, DRA RT driver, `rt-budget-seed.sh` (see RQ1_final/os-experiments/notes.md). Image `pippina2/rq1final-probe:v1`.
1. Put the node in the all-defaults state: `./apply.sh d07-model1` (agent), then `levers/defaults.sh <ns> apply`, reboot, `levers/defaults.sh <ns> status`
   must show no isolcpus/nohz_full/rcu_nocbs/mitigations=off, no containment, THP always, SMT on. Deploy agents with `SKIP_FREQ_PIN=1`.
2. Apply the lever of the configuration (table above), reboot if needed, check with `levers/lever.sh <ns> <lever> status`, run `rt-budget-seed.sh` again after every reboot.
3. `./run_config.sh dNN <node> 1` (single-core then multi-core, results in `results/dNN-model{1,5}_round1`). d07: `U_MAX=0.7 ./run_config.sh d07 <node> 1`
   (U = 0.94 was not run in the all-defaults state of RQ1_final; keep CV_THRESHOLD as there if calibration gates fail).
4. Repeat for round 2..4 (`./run_config.sh dNN <node> 2`); reseed the RT budget if the node was idle for long.
5. Between configurations on the same VM: `levers/lever.sh <ns> <lever> restore` (+ reboot for grub levers) back to the all-defaults state, then check `status`.

## Suggested use of 5 VMs
d07 (all defaults) is NOT rerun: the reference is the existing RQ1_final all-defaults data (scenario 07, rerun with the full-isolation K table). Each VM must still
start in the all-defaults state (check with `levers/lever.sh ... status`), because that is what d07 measured.
Grub levers need a reboot, the live ones do not, so the live ones can share a VM: VM1: d04, then d05, then d08 (apply, run, restore each) | VM2: d01 | VM3: d02 | VM4: d03 | VM5: d06.
Rounds 1-4 per configuration, 4 rounds as in RQ1_final.

## Things to check before trusting a configuration
- `levers/lever.sh ... status` shows only the intended lever on; the same for the reference (d07) at the start.
- Frequency: governor/turbo are the OS defaults in every configuration except d08 (the agent pins them unless SKIP_FREQ_PIN=1).
- Multi-core: `RT_CPUSET` is recorded as `1-3` by the driver and `taskset -c 1-3` is the range {1,2,3}, as in all RQ1_final multi-core runs, so a thread may also run on cpu 2
  (SMT sibling of cpu 3). Kept for comparability; unverified (`taskset -cp <pid>` inside a pod shows it).
- Single-core model1 requests cpu 2; with isolcpus/nohz_full/rcu_nocbs off, cpu 2 is a normal cpu in d07/d04/d05/d06/d08.
