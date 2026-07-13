"""
rtmetrics — shared metrics-analysis library for the RQ1 deterministic-probe models
(model1_1 / model2 / model3 / model4). model1 is independent and does NOT use this.

Submodules:
  metrics     percentiles, per-job stats, reservation supply (alpha/Delta)
  covariates  per-job window join to the sampler's covariate streams
  plotting    shared plotting style + readers + helpers

Usage from a model script (siblings of common/):
    import sys; from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "common"))
    from rtmetrics import metrics, covariates, plotting
"""
from . import metrics, covariates, plotting  # noqa: F401

__all__ = ["metrics", "covariates", "plotting"]
