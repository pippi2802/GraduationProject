# common/ — shared workload + metrics analysis (RQ1)

The four deterministic-probe models — **`model1_1`, `model2`, `model3`, `model4`**
— run the **same workload** and **analyse the same metrics**, differing only in
configuration, topology and neighbours. To keep that DRY, the reusable pieces live
here, **outside** the model folders.

> **`model1` is independent** and does NOT use this directory — it has its own
> (rt-app based) workload and analysis.

## Contents

```
kernel/       THE WORKLOAD — deterministic dense matmul probe (matmul.c + Dockerfile + build.sh + Makefile)
sampler/      measurement — privileged hostPID covariate/supply sampler (stdlib python):
  sampler.py                     the sampler itself
  sampler-daemonset.yaml.template per-model DaemonSet template (@@MODEL@@/@@HOSTDIR@@/@@NODE_MODEL@@)
  apply.sh <model> [hostdir] [node-model]  renders + applies it, loads sampler.py as a ConfigMap
rtmetrics/    metrics-analysis library (importable package):
  metrics.py      pct(), job_stats(), reservation_supply(), supply_from_server()
  covariates.py   per-job window join (join_percell for 2/3/4; join_model1_1 for model1_1)
  plotting.py     shared style, CSV readers, CCDF, save()
```

## How a model uses it

Each model keeps its own `config.yaml`, `manifests/`, orchestrator
(`run_modelN.py`), `analyze.py` and figure set (`plots/plot_all.py`), but pulls the
shared code from here:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "common"))  # RQ1/common
from rtmetrics import metrics, covariates, plotting
```

- **Workload/image:** every participating `config.yaml` sets the same
  `image.full_ref` (`pippina2/model1-kernel:v0.1.0`), built once via
  [kernel/build.sh](kernel/build.sh).
- **Calibration:** `model1_1` still owns the calibration
  [`k_table.json`](../model1_1/calibration); `model2/3/4` REUSE it (they don't
  recalibrate — each model's `config.yaml` sets `calibration.source_table` to it and
  the model's `modelNlib.py` scales it, since `C` is linear in `K`).
- **Sampler:** the DaemonSet is now shared too — run `sampler/apply.sh <model>`
  (e.g. `sampler/apply.sh model2`, or `sampler/apply.sh model1-1 model1_1 model1`
  for model1_1's irregular naming). It renders
  [sampler/sampler-daemonset.yaml.template](sampler/sampler-daemonset.yaml.template)
  and loads [sampler/sampler.py](sampler/sampler.py) as a ConfigMap; streams land
  in `/var/lib/<model>/samples`. Only `node-prep/` stays per-model.

## What stays per-model (NOT shared)

Configuration and the parts that genuinely differ: `config.yaml`, `manifests/`,
`node-prep/`, `run_modelN.py`, the specific figures in `plots/plot_all.py`, and the
per-variant summary layout in `analyze.py`. Those import the shared primitives above
rather than duplicating them.
