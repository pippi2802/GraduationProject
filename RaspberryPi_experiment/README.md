# RaspberryPi (bare metal) — same periodic workload, no Kubernetes

Mirror of the [`ContendedAKS_experiment/`](../ContendedAKS_experiment) but
executed directly on a Raspberry Pi running Ubuntu (ARM64). The goal is to
isolate the **scheduler / OS** contribution to deadline misses from the
**cloud-platform** contribution (host kernel preemption, hypervisor steal,
node churn, neighbouring pods, AKS DaemonSets, etc.).

The CPU work, periods, utilization and miss-detection logic are identical
to the AKS run, so results are directly comparable.

## Hardware target

The AKS node was `Standard_D2ps_v6` = **2 vCPUs, ARM64 (Ampere Altra)**.
Closest Pi to use:

- **Raspberry Pi 5** — 4× Cortex-A76 @ 2.4 GHz (ARM64).
- **Raspberry Pi 4** — 4× Cortex-A72 @ 1.8 GHz (ARM64). Also fine.

Both Pis have **4 cores**, so the same workload at U = 1.60 would only
load 40 % per core — much less contention than the AKS run, which would
hide the comparison. To keep the contention scenario identical we **pin
the workload to 2 cores** with `taskset -c 0,1` (configurable in
`scripts/run_experiment.sh`).

We also run the workload **natively, with no container and no
Kubernetes**. The point is to isolate the OS/CPU baseline; adding
containers here would just re-introduce one of the variables we're trying
to remove.

OS: Ubuntu Server 24.04 LTS arm64 (any recent Ubuntu / Raspberry Pi OS
works).

## Workload

Same `rt_multi_periodic.c` as the AKS experiment. We launch **two
processes** (`procA`, `procB`), each spawning 3 periodic threads — exactly
matching the "two containers, three threads each" configuration on AKS.

| Task | T (ms) | C (ms) | U  |
|------|-------:|-------:|----:|
| 0    | 20     | 5      | 0.25|
| 1    | 50     | 15     | 0.30|
| 2    | 100    | 25     | 0.25|

Per process U = 0.80, total U = 1.60 on 2 pinned cores (~80 %), identical
to the AKS run.

## Files

- [`rt_multi_periodic.c`](rt_multi_periodic.c) — periodic workload (copy of
  the AKS version).
- [`scripts/build.sh`](scripts/build.sh) — `gcc -O2 -pthread`.
- [`scripts/run_experiment.sh`](scripts/run_experiment.sh) — pins to 2 CPUs
  with `taskset`, launches both processes in parallel, waits, copies CSVs
  into `results/<timestamp>/`.
- [`analyze.py`](analyze.py) — identical to the AKS one (per-task
  mean/var/percentiles + miss rate + CDF).

## Run it

On the Pi:

```bash
sudo apt-get update && sudo apt-get install -y build-essential python3-pip
pip3 install numpy pandas matplotlib --break-system-packages

cd RaspberryPi_experiment
./scripts/build.sh
chmod +x scripts/*.sh
```

### Pre-run tuning (important)

Without this the Pi will dynamically lower CPU frequency between task
invocations and ramp it back up when work arrives, which adds artificial
variance unrelated to scheduling.

```bash
# 1. Pin all CPUs to the maximum frequency
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
# verify
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor   # -> performance

# 2. (optional) silence background services that compete for the CPU
sudo systemctl stop snapd cron unattended-upgrades 2>/dev/null || true
```

### Run

```bash
./scripts/run_experiment.sh                 # uses cores 0,1 by default
# or with custom output dir / pinning:
./scripts/run_experiment.sh results/test1 0,1

python3 analyze.py results/<timestamp>/
```

## Comparing with the AKS run

Drop the AKS `results/run1/` and the Pi `results/<timestamp>/` next to
each other and look at:

- **`exec_var`** — should be tiny in *both* cases (deterministic work).
- **`resp_var`, `p99(resp)`, `max(resp)`** — should be **lower on the Pi**
  if cloud-side jitter (steal time, neighbours, etc.) is the dominant
  source. If they're similar, CFS itself is the bottleneck.
- **`miss_rate`** — same direction.
- **`cA_proc_stat.csv` / `cB_proc_stat.csv`** on the AKS side: any non-zero
  *steal* delta indicates hypervisor-induced preemption that the Pi
  cannot exhibit (no hypervisor).

> Tip: keep period/runtime/iters identical between the two experiments
> when reporting — the analyzer doesn't care, but apples-to-apples
> comparison requires it.
```bash
cd RaspberryPi_experiment
sudo apt-get install -y build-essential python3-pip
pip3 install numpy pandas matplotlib --break-system-packages
./scripts/build.sh
chmod +x scripts/*.sh
./scripts/run_experiment.sh           # creates results/<timestamp>/
python3 analyze.py results/<timestamp>/
```