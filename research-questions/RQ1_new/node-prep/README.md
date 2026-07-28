# node-prep — pin the frequency, expose results

One privileged DaemonSet per model node that does two jobs:

1. **Pins CPU frequency** — sets the `performance` governor, disables turbo/boost,
   and pins `scaling_max_freq` to the min where exposed. This makes the probe's
   `C` (CPU-time) reproducible: without it, the same work runs ~1.5× slower at
   base clock than at turbo, so cells randomly overran their budget. *(Best effort
   — an Azure guest may refuse some writes; the agent logs the resulting state so
   you can confirm what actually held.)*
2. **Exposes the results** — mounts the model's host results path so `run_sweep.py`
   can `cat` each cell's `jobs.csv` off the node (no per-cell sampler needed).

## Use
```bash
cd node-prep
./apply.sh model1        # renders + applies for that model's node

# confirm the pin took:
kubectl -n rq1-model1 exec ds/rq1-agent -- \
  cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor      # -> performance
kubectl -n rq1-model1 exec ds/rq1-agent -- \
  cat /sys/devices/system/cpu/intel_pstate/no_turbo              # -> 1
```

## Stronger isolation (optional, needs a reboot)
For a genuinely quiet RT core, boot the worker with `isolcpus=`, `nohz_full=`,
`rcu_nocbs=` on the RT core and keep its SMT sibling idle. That's a node cmdline
change outside this harness; the agent's frequency pin is the reboot-free minimum.
