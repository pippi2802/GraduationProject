# SR-IOV / Accelerated Networking probe

Standalone, timeboxed spike. **Not part of RQ1.** Purpose: cheaply check
whether Azure Accelerated Networking (SR-IOV) meaningfully reduces
node-to-node network latency/jitter, before deciding whether it's worth
building into a real experiment.

No calibration, no H-CBS, no `dra-rt-driver` involved — this only measures
raw network path latency with `ping`/`iperf3` between two nodes.

## Timebox

**1-2 days, hard stop.** If you're not done in 2 days, stop and drop it.

## Decision rule (set BEFORE looking at results)

"Important" means: RTT p50 or p99, or iperf3 jitter, drops by **>50%**
comparing accelerated-on vs accelerated-off. Anything smaller is noise-level
for this kind of test — don't rationalize a small improvement into "worth
pursuing."

If it clears the bar: re-check the calendar before committing to building a
real cross-VM workload experiment (2-3+ weeks, separate scope from RQ1).
If it doesn't clear the bar, or the timebox runs out: drop it, keep it as a
one-paragraph future-work mention citing the RT-cloud survey paper.

## What you need

Two VMs/nodes in two conditions:
- **accel_off**: current node pool (or any VM SKU with Accelerated Networking
  disabled)
- **accel_on**: a node pool on an Accelerated-Networking-capable SKU
  (most current D/E/F-series v3+) with it explicitly enabled

You don't need your RT-patched kernel image for this — plain node pools are
fine, this doesn't touch scheduling at all.

## How to run

1. Label two nodes so the manifests can pin pods to them:
   ```
   kubectl label node <server-node> sriov-probe-role=server --overwrite
   kubectl label node <client-node> sriov-probe-role=client --overwrite
   ```

2. Run one full pass per condition:
   ```
   CONFIG_LABEL=accel_off ./run_probe.sh
   # ... recreate node pool with Accelerated Networking on, re-label nodes ...
   CONFIG_LABEL=accel_on ./run_probe.sh
   ```

3. Compare:
   ```
   ../../.venv/bin/python3 compare.py results/accel_off_* results/accel_on_*
   ```
   (adjust the venv path if this project's venv lives elsewhere)

Each run writes `results/<CONFIG_LABEL>_<timestamp>/{ping.log,iperf.json}`.
