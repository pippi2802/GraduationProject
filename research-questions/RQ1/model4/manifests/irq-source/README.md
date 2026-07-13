# Model 4 IRQ source (optional network-I/O generator)

Azure-guest interrupt controllability is limited and **NIC-dependent**, and the
node's **ambient** IRQ rate is often too low for steering to show an effect. This
optional generator produces **real, steerable NIC interrupts** so the `on` vs `off`
difference is observable.

## What it is

An **iperf3 UDP flood** between two **unreserved** pods on the `model4` node,
**outside** the RT reservation:

| pod | role |
| --- | ---- |
| `…-irqsrc-server` | `iperf3 -s` on the node NIC (`hostNetwork`) |
| `…-irqsrc-client` | `iperf3 -c <server-ip> -u -b <bitrate> -l <len>` in a restart loop |

Small UDP packets (`irq_source.packet_len_bytes`, default 64) maximise the **packet
rate ⇒ RX IRQ/softirq rate**. The bitrate is the `--irq-load` knob:

| `--irq-load` | iperf3 `-b` |
| ------------ | ----------- |
| `off` | generator disabled (ambient IRQ only) |
| `light` | `50M` |
| `medium` (default) | `200M` |
| `heavy` | `0` (unlimited — max packet rate) |

`${SERVER_IP}` is filled by `run_model4.py` from the server pod's `hostIP` at apply
time; the pods are deleted with the sweep.

## Enable / disable

Controlled by `irq_source.enabled` in [config.yaml](../../config.yaml) (default
**enabled** — the prompt's third question). Disable it if the node already has a
high steerable IRQ rate:

```yaml
irq_source:
  enabled: false
```

or per-run: `run_model4.py --irq-load off`.

## Honest limitation

If the server and client co-locate and the traffic stays in-kernel (veth/loopback),
it may drive **softirqs** more than hardware NIC IRQs. `hostNetwork: true` routes it
through the node NIC to maximise real virtio IRQs, but on some AKS SKUs the movable-
IRQ set is still small — `run_model4.py`'s preflight will **stop and ask** if the RT
core's IRQ rate cannot be raised (`--force-lowirq` to override). This is recorded,
not hidden.
