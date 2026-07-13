# Model 3 interferer (sibling arm only)

The interferer is what makes the **sibling** arm a *treatment*: it runs the **same
fixed matmul** on the RT container's **HT sibling logical CPU** so it competes with
the RT task for the shared physical core's execution units (ALU / FPU / L1 / L2) —
the hyper-thread interference Model 3 measures.

## Design (why these choices)

| property | value | why |
| -------- | ----- | --- |
| reservation | **none** (unreserved pod) | competes only at the **hardware-thread** level, never at the CBS level |
| scheduler | `--priority 0` → **SCHED_OTHER (CFS)** | *not* subject to RT-bandwidth throttling; uses all spare cycles on its logical CPU |
| pinning | `taskset -c <SIBLING_CPU>` | the RT core's **HT sibling**, resolved at runtime |
| kernel | same `matmul`, same `M`, same seed | CPU-compute only — **no** memory-bandwidth / LLC stressor (thesis scope) |
| intensity | `--sibling-load {off,light,medium,saturating}` | the swept dose knob |

## Intensity knob (`--sibling-load`)

Intensity is a **duty cycle** over a fixed interferer period
(`interferer.interferer_period_us`, default 10 ms):

| level | duty | how it runs |
| ----- | ---- | ----------- |
| `off` | 0.0 | no interferer (≡ physical arm) |
| `light` | 0.25 | `K` reps fill 25 % of each period |
| `medium` | 0.6 | `K` reps fill 60 % of each period |
| `saturating` (default) | 1.0 | `--period-us 0` → **continuous back-to-back** |

`K` for `light`/`medium` is derived from the reused per-scale slope
(`busy_us = duty × period`, `K = round(busy_us / slope)`); see
[`model3lib.interferer_spec`](../model3lib.py).

## How true HT co-location is guaranteed

The rt-DRA driver is **SMT-blind** and worst-fit — it may pin the RT container to
*any* logical CPU. So [`run_model3.py`](../run_model3.py):

1. applies the RT reservation and waits until it is **Ready**,
2. reads the RT container's **actual `RT_CPUSET`** (e.g. cpu1),
3. resolves that CPU's **HT sibling** from the node-prep `cpu-map.json`
   (`thread_siblings_list`, e.g. cpu0 on D4s_v5 where core A = {0,1}),
4. launches this interferer **`taskset`-pinned to that sibling CPU**.

So co-location on the **same physical core** is *guaranteed* regardless of the
driver's placement, and both CPUs are recorded in `cell.json` for offline audit.

## Template

[`interferer.template.yaml`](interferer.template.yaml) — `${SIBLING_CPU}` is filled
by `run_model3.py` at apply time. `render.py --all` also emits committed
per-`(scale, load)` copies (`<scale>-<level>.yaml`) with the literal placeholder
`<SIBLING_CPU>` for inspection.

## Dose-response figure

Sweep the knob at the fixed `interferer.dose_response_utilization` (default `U=0.8`)
by running the sibling arm once per level into its own time-block, then pass them
to the plotter:

```bash
python ../run_model3.py --arm sibling --sibling-load light      --timeblock tb-light  --only-u 0.8
python ../run_model3.py --arm sibling --sibling-load medium     --timeblock tb-med    --only-u 0.8
python ../run_model3.py --arm sibling --sibling-load saturating --timeblock tb-sat    --only-u 0.8
# analyze each, then:
python ../plots/plot_all.py --timeblock tb-sat --dose-timeblocks tb-light tb-med tb-sat
```
