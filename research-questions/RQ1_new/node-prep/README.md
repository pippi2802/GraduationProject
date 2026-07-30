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

## Core isolation (`isolcpus`/`nohz_full`/`rcu_nocbs`, needs a reboot)
For a genuinely quiet RT core, boot the worker with `isolcpus=`, `nohz_full=`,
`rcu_nocbs=` on every cpu except one kept for kubelet/sshd/housekeeping. This is
now automated by `isolate.sh` (still **not** applied automatically by `apply.sh`,
since it requires a reboot that evicts every pod on the node):

```bash
bash node-prep/apply.sh model1          # agent must be up first
bash node-prep/isolate.sh model1 apply  # stages isolcpus=/nohz_full=/rcu_nocbs=
                                         # in /etc/default/grub via nsenter into
                                         # the host; does NOT reboot

# reboot the node yourself (Azure Portal / az vm restart / ssh + sudo reboot),
# then confirm it took effect:
bash node-prep/isolate.sh model1 status

# to undo (also needs a reboot to take effect):
bash node-prep/isolate.sh model1 restore
```

By default cpu0 is kept OUTSIDE isolation for the OS; every other logical cpu on
the node is isolated. Do not `PIN_RTCPU`/place a target or competitor on cpu0 once
isolation is active — pass a different `keep_cpu` to `isolate.sh` if your sweep
needs cpu0 specifically. A single backup of the original `/etc/default/grub` is
kept at `/etc/default/grub.rq1.orig` on the node; `restore` reverts to it.

This does not make the RT core immune to Azure/hypervisor-level interference —
that's the thing RQ1 is measuring — it only removes generic in-guest Linux
housekeeping noise (timer ticks, RCU callbacks, reschedule IPIs) from the
isolated core, so the baseline's tail reflects cloud effects more cleanly and is
more reproducible run-to-run, which is what RQ2's tail-based parameter
derivation needs.
