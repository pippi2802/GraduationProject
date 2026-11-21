# Isolation validation: interrupts on the RT core

`check_isolation.sh <ns> <label> <rt_cpus> [secs=40] [task|idle]` measures, through the rq1-agent of the namespace, the interrupts per second on the RT cores
(delta of `/proc/interrupts`: LOC, HVS, HYP, RES, CAL, ...), the threads seen there (`ps -eLo psr,comm`), and once the boot state (isolated, nohz_full,
IRQ affinities, rcuo* affinity). Output in `results/<label>.txt`. Expectation under `nohz_full` with one task running: timer ~1/s on the RT core
(a few hundred per second without it, depending on CONFIG_HZ). With `mode=task` it waits for the `workload` process and skips WARM=15 s of start-up.

Single-core task = model1, RT core = the cpu of the claim (check with the pod's `RT_CPUSET`; model1 claims cpu 2, `requestedCpus: [2]`). Tight scale: a cell runs ~50 s, so the window (40 s) fits.

## Runs per VM
1. idle (no task), `<cfg>_idle`, with rt_cpus = 2
2. task, one run per U in 0.1 0.5 0.7 0.94: terminal A starts the check, terminal B starts one cell:
```
# A
./check_isolation.sh <ns> <cfg>_U0.1 2 40 task
# B  (one utilization, tight only, one round)
cd ../ && U_LIST=0.1 OUT_TAG=_iso RESULTS_ROOT=results_iso ./run_job.sh model1 tight
```
(second argument = scale; scratch RESULTS_ROOT so the data is not mixed with the experiments)
2b. busy: `./check_isolation.sh <ns> <cfg>_busy 2 40 busy` (spin loop, no timers; the clean nohz_full test)
3. repeat for the full default (d07 / `all defaults`) VM, and, if wanted, once for `nohz_full removed` (d02) as the contrast.

## Does the frequency pinning do anything? (`check_frequency.sh <ns> <label> <cpu> [secs]`)
Static state (driver, governor, turbo, MHz, flags, perf cycles) plus a timing test: a fixed amount of integer work pinned to the cpu, for three phases
(as configured / governor powersave + turbo allowed / restored). Settings are restored. If A and B agree within noise the guest setting has no effect on
the hardware (Azure decides the clock); the per-10 s medians in phase A show drift. Run on an idle node (no workload pod).
