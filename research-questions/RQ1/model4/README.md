# Model 4 — IRQ-steering RT experiment (KubeDeadline / RQ1)

Is **interrupt affinity** a first-class, *controllable* determinant of real-time
jitter in the cloud? IRQ interference steals microseconds from **inside** the
reservation window and delays budget replenishment (a `Δ` / `α`-delivery effect), so
it lands in the **delay layer** `R − C`. Because it is **absolute-time**, it is
period-**dependent as a fraction**: severe at tight (10 ms), largely absorbed at
soft (100 ms) — a delay-layer break that **FADES at the soft scale**, the *mirror
image* of Model 3's period-independent execution-layer break.

Model 4 uses the **same** deterministic matrix-multiply probe, the **same** two-clock
delay decomposition, the **same** reused calibration, and the **same** shared analysis
(`../common/rtmetrics`) as [`../model1_1`](../model1_1) / [`../model2`](../model2) /
[`../model3`](../model3) — a different node label and a different question.

> **VARIANCE IS THE MEASUREMENT.** The probe (fixed `M×M` double matmul, fixed data,
> `K` reps/job) has near-zero intrinsic variance. `C = CLOCK_THREAD_CPUTIME_ID` does
> **not** advance while the thread is off-core servicing an IRQ, so `C` stays flat
> and the interrupt-induced jitter shows up cleanly in `R − C`.

## The two arms

| arm | flag | what it does | expect |
| --- | ---- | ------------ | ------ |
| **off** (reference) | `--arm off` | steer steerable device IRQs **away** from the RT core onto the other physical core | tail collapses toward the clean baseline |
| **on** (treatment) | `--arm on` | steer steerable device IRQs **onto** the RT core | tail inflates, correlated with per-core IRQ CPU-time |

The RT reservation + reused `K` are **identical** across arms, so the R-tail
difference is a **pure IRQ effect**.

## What IS / ISN'T steerable in an Azure guest (stated limitation)

Interrupt controllability in an Azure VM is **limited and NIC-dependent**:

- **Steerable:** many device lines (virtio-net / storage) expose a writable
  `/proc/irq/<n>/smp_affinity_list`. [`irq-control/steer.sh`](irq-control/steer.sh)
  matches them by descriptor (`irq_control.steerable_patterns`), writes the target
  cpu, and **verifies the write took**.
- **NOT steerable:** **managed** IRQs (kernel-owned) silently reject affinity writes;
  `LOC`/`RES`/`IPI`/timer "interrupts" are not device IRQs and are never movable.
  These are **recorded honestly** (`not_steerable_count` in `irq-map.json`).
- If the RT core's IRQ rate **cannot** be meaningfully raised in the `on` arm,
  `run_model4.py` runs an **IRQ preflight** and **STOPS and asks** (override with
  `--force-lowirq`) rather than silently producing a null result.
- To *guarantee* an observable effect, an **optional IRQ source**
  ([`manifests/irq-source`](manifests/irq-source)) generates real, steerable NIC
  interrupts (iperf3 UDP flood, rate = `--irq-load`).

`irqbalance` is **paused** (`SIGSTOP`) during a run so affinity stays stable, and
**resumed** + affinity **restored** at the end (always, via `try/finally`).

## Layout

```
config.yaml            all parameters (DRY): scales, U grid, arms, IRQ control/source, reused calibration/image
model4lib.py           derivations (Q, reused K + C_baseline, cell grid, irq-source rate, names, paths)
node-prep/             detect-siblings (Azure-safe detect-only) + guarded offline + DaemonSet
irq-control/           steer.sh + restore.sh + privileged DaemonSet (the two arms)
manifests/
  template/            rt-cell template + render.py
  off/ on/{tight,soft} committed rendered RT cells (render.py --all)
  irq-source/          optional iperf3 UDP generator template (+ committed per-load)
run_model4.py          orchestrator: --arm {off,on}, --irq-load, steer + preflight + sweep + restore
analyze.py             offline reduction: join covariates + tail + supply -> model4-summary.csv / model4-tail.csv
plots/plot_all.py      figure set -> figures/ (PNG+PDF); reuses ../common/rtmetrics/plotting
results/               git-ignored
```

## Prerequisites

- A node labelled `experiment-model=model4`
  (`kubectl label node <n> experiment-model=model4`).
- The rt-DRA driver installed (`*.example.com` API), as in `../model1`.
- **Model 1_1 calibration present**: `../model1_1/calibration/k_table.json`
  (`python ../model1_1/calibration/calibrate.py`).
- The `../common` kernel image pushed (`pippina2/model1-kernel:v0.1.0`).
- `kubectl` context pointing at the rt-cluster.

## Run it

**1. Apply the DaemonSets** (once):

```bash
node-prep/apply.sh                  # detect-only cpu-map.json (per-core siblings + core_of)
../common/sampler/apply.sh model4   # shared sampler (incl. per-cpu irq/softirq) -> /var/lib/model4/samples
irq-control/apply.sh                # steer.sh / restore.sh host executor
```

**2. Sweep each arm into ONE time-block** (cells sequential, delete+recreate):

```bash
TB=tb-$(date +%Y%m%d-%H%M)
python run_model4.py --arm off --irq-load medium --timeblock $TB
python run_model4.py --arm on  --irq-load medium --timeblock $TB
```

Useful flags: `--scales tight`, `--only-u 0.9 0.94`, `--n-jobs 50000` (deepen tails),
`--force-lowirq` (proceed past a null preflight), `--dry-run`.

**3. Analyze + plot** (both arms in the time-block):

```bash
python analyze.py        --timeblock $TB
python plots/plot_all.py --timeblock $TB
```

**Dose-response** (on-arm tail vs IRQ load) — one time-block per load, then:

```bash
for L in light medium heavy; do
  python run_model4.py --arm on --irq-load $L --timeblock tb-$L --only-u 0.8
  python analyze.py --timeblock tb-$L
done
python plots/plot_all.py --timeblock tb-medium --dose-timeblocks tb-light tb-medium tb-heavy
```

Preview the derived grid + reused K without touching the cluster:

```bash
python model4lib.py --arm on
```

## Results layout

```
results/<timeblock>/
  off/<scale>/U<u>/jobs.csv                   per-job C,R,delay,miss (reference arm)
  on/<scale>/U<u>/jobs.csv                    per-job (treatment arm)
  {off,on}/<scale>/U<u>/jobs_with_covariates.csv   + per-job irq_us/softirq_us/steal_us
  {off,on}/<scale>/U<u>/cell.json             provenance: irq_map (steered lines), preflight, /proc/interrupts snapshot
  samples/{cpu,tasks,server}.csv              continuous covariate streams
  model4-summary.csv                          one row per (arm,scale,U)
  model4-tail.csv                             one row per (scale,U): off vs on tail + IRQ attribution
  figures/*.png (+pdf)
```

## Figures

`fig_r_ccdf_<scale>_U<u>` (R CCDF off vs on, log tail), `fig_tail_miss_vs_u_<scale>`,
`fig_cross_scale_inflation` (**fades at soft** ⇒ delay layer), `fig_irq_attribution`
(R−C vs I_IRQ positive; vs steal flat), `fig_delta_eff_vs_u_<scale>`
(replenishment jitter), `fig_mean_excess_on` (bounded vs heavy-tailed),
`fig_dose_response` (R tail vs `--irq-load`).

## Hard-won caveats baked in (shared with Model 1_1 / 2 / 3)

- **Never offline a vCPU on D4s_v5** — wedges the VM and zeroes the RT budget chain.
  `node-prep/offline-siblings.sh` is guarded (`FORCE=1`, not Azure-safe).
- **`U ≥ 0.95` is unschedulable** (driver admits only `reqUtil < 950‰`).
- **Read counters via the sampler / irq-control pods**, never `kubectl exec` a FIFO-90 cell.
- **N=5000 ⇒ stable p99, not p99.9**; IRQ tails may be under-sampled — deepen with `--n-jobs`.
- **IRQ steerability is limited in Azure guests** — the preflight refuses to produce
  a silent null; enable the IRQ source or `--force-lowirq` deliberately.

## Confirmed inputs (the prompt's three questions)

1. **KubeDeadline reservation API** — rt-DRA `RtClaimParameters`
   (`rt.resource.example.com/v1alpha1`): `runtime→Q`, `period→P`, `count→m`, µs;
   class `rt.example.com`; admission `reqUtil < 950‰`. **Confirmed** against
   [`workloads/rt-dra-verify/rt-verify.yaml`](../../../workloads/rt-dra-verify/rt-verify.yaml).
2. **Container image** — reuse `pippina2/model1-kernel:v0.1.0` (same `matmul` probe).
3. **Optional network-I/O IRQ source** — **enabled by default**
   (`irq_source.enabled: true`, `--irq-load medium`) because the ambient Azure IRQ
   rate is usually too low to show an effect. Disable with `irq_source.enabled:
   false` or `--irq-load off` if the node already has a high steerable IRQ rate.
