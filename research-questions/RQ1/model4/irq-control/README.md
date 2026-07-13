# Model 4 IRQ control (steer + restore)

The IRQ-control plane is what makes the two arms *arms*: it moves **steerable device
IRQs** onto the RT core (`on`) or away onto the other physical core (`off`), and
keeps that affinity stable during the run.

## What it does

| step | how |
| ---- | --- |
| pause `irqbalance` | `pkill -STOP -x irqbalance` (hostPID) so it does not fight our affinity; recorded as `irqbalance_was_running` |
| classify IRQ lines | read `/proc/interrupts`; a line is a candidate if its **descriptor** matches `irq_control.steerable_patterns` (virtio/hyperv/mlx/eth/nvme/…) |
| steer | write the target cpu to `/proc/irq/<n>/smp_affinity_list` **and verify it took** (managed IRQs silently reject) |
| record | write `irq-map.json` (arm, target cpu, steered lines, not-steerable count, irqbalance state) |
| restore | [`restore.sh`](restore.sh): reset affinity to all online CPUs + `SIGCONT` irqbalance |

`/proc/irq/<n>/smp_affinity_list` is **kernel-global**, so a privileged container can
rewrite the host's IRQ routing; `hostPID` lets it pause/resume the host irqbalance.

## Honest Azure-guest limitation (stated, not hidden)

Interrupt controllability in an Azure VM is **limited and NIC-dependent**. Many
lines are **managed** (kernel-owned) and silently reject affinity writes; timer /
IPI / RES / LOC "interrupts" are **not device IRQs** and are never steerable. So:

- `steer.sh` **detects and logs** exactly which lines were steerable
  (`steered_irqs`) and how many were not.
- `run_model4.py` runs a **preflight**: it measures the RT core's IRQ rate in the
  `on` arm; if steering does not raise it by at least
  `irq_control.min_effective_irq_delta_per_s`, it **STOPS and asks** (override with
  `--force-lowirq`) rather than silently producing a null result.
- To *guarantee* an observable effect, enable the **optional IRQ source**
  ([`../manifests/irq-source`](../manifests/irq-source)) — an iperf3 UDP flood that
  generates real, steerable NIC interrupts.

## Manual use

```bash
kubectl -n model4 exec ds/model4-irq-control -- \
  env ARM=on RT_CPU=0 OTHER_CPU=2 bash /tmp/steer.sh
kubectl -n model4 exec ds/model4-irq-control -- bash /tmp/restore.sh
```
