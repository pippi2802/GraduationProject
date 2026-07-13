#!/usr/bin/env python3
"""
model3lib — shared helpers for the Model 3 (hyper-thread vs physical-core) harness.

Single place that loads config.yaml and derives everything that must stay DRY:
per-cell Q from U and P, the reused Model 1_1 calibration (K + C_baseline, read
from ../model1_1/calibration/k_table.json — C is linear in K so the table's exact
grid K is used and its median_C_us is the C_baseline reference), the KubeDeadline
reservation (Q,P,m), the interferer duty/K for each --sibling-load level, the two
pinning ARMS' cell grids, and directory/path/name templates.

NO recalibration happens in Model 3: per the experiment directive the workload
calibration is REUSED from Model 1_1. The SAME K is used for BOTH arms so that
C(sibling)/C(physical) is a pure hyper-thread inflation factor.

Every Model-3 script (renderer, orchestrator, analyzer, plots) imports from here so
a parameter change happens in exactly one file (config.yaml).
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML required. Install with: pip install pyyaml\n")
    raise

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.yaml"


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
def load_config(path=None) -> dict:
    p = Path(path) if path else DEFAULT_CONFIG
    with open(p, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["_config_path"] = str(p)
    return cfg


# --------------------------------------------------------------------------- #
# Derivations
# --------------------------------------------------------------------------- #
def derive_q_us(u: float, period_us: int) -> int:
    """Q is DERIVED, never hardcoded:  Q_us = round(U * P_us)."""
    return int(round(u * period_us))


def u_label(u: float) -> str:
    """Stable filesystem-safe label for a utilization, e.g. 0.94 -> '0.94'."""
    return ("%g" % u)


def scale_dir(cfg: dict, scale: str) -> str:
    return cfg["scales"][scale]["dir"]


def reservation_qp(cfg: dict, q_us: int, period_us: int):
    """Return (runtime, period) in the configured reservation units."""
    units = cfg["kubedeadline_reservation_spec"]["units"]
    if units == "microseconds":
        return q_us, period_us
    if units == "milliseconds":
        return int(round(q_us / 1000)), int(round(period_us / 1000))
    if units == "nanoseconds":
        return q_us * 1000, period_us * 1000
    raise ValueError(f"unknown reservation units: {units}")


# --------------------------------------------------------------------------- #
# REUSED Model 1_1 calibration  (exact grid K + C_baseline; NO recalibration)
# --------------------------------------------------------------------------- #
def source_table_path(cfg: dict) -> Path:
    return (HERE / cfg["calibration"]["source_table"]).resolve()


def load_source_ktable(cfg: dict) -> dict:
    """Load Model 1_1's k_table.json (reused). Empty dict if missing (dry-run ok)."""
    p = source_table_path(cfg)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _scale_slope(ktab: dict, scale: str):
    """slope = median_C_us / K for the given scale (C is linear in K).

    Median of (median_C_us / K) over every calibrated cell of that scale. Returns
    None if the table has no such cells. Used for OFF-grid targets (the interferer
    duty). Grid cells use the table's exact K/median directly.
    """
    slopes = []
    for _, e in ktab.items():
        if e.get("scale") != scale:
            continue
        K = e.get("K")
        c = e.get("median_C_us")
        if K and c and K > 0:
            slopes.append(c / K)
    if not slopes:
        return None
    return statistics.median(slopes)


def grid_entry(ktab: dict, scale: str, q_us: int):
    """Return the reused table entry (K, median_C_us=C_baseline, cv) for a grid
    cell whose Q matches, else None."""
    for _, e in ktab.items():
        if e.get("scale") == scale and e.get("Q_us") is not None:
            if abs(float(e["Q_us"]) - q_us) <= 0.5:
                return e
    return None


def k_for_u(cfg: dict, scale: str, u: float, ktab: dict | None = None):
    """Reused K for a full-utilisation-U cell (target C = round(U*P))."""
    ktab = ktab if ktab is not None else load_source_ktable(cfg)
    period_us = cfg["scales"][scale]["period_us"]
    q_us = derive_q_us(u, period_us)
    e = grid_entry(ktab, scale, q_us)
    if e and e.get("K"):
        return int(e["K"])
    # fall back to the per-scale linear slope (off-grid tolerant, dry-run safe)
    slope = _scale_slope(ktab, scale) if ktab else None
    if not slope or slope <= 0:
        return None
    min_reps = int(cfg["calibration"].get("min_reps", cfg["kernel"].get("min_reps", 1)))
    return max(min_reps, int(round(q_us / slope)))


def c_baseline_for_u(cfg: dict, scale: str, u: float, ktab: dict | None = None):
    """Reused C_baseline (median_C_us on an isolated core) for a grid cell."""
    ktab = ktab if ktab is not None else load_source_ktable(cfg)
    period_us = cfg["scales"][scale]["period_us"]
    e = grid_entry(ktab, scale, derive_q_us(u, period_us))
    return float(e["median_C_us"]) if e and e.get("median_C_us") is not None else None


# --------------------------------------------------------------------------- #
# Interferer duty -> (period_us, K)  for a --sibling-load level
# --------------------------------------------------------------------------- #
def interferer_spec(cfg: dict, scale: str, level: str, ktab: dict | None = None) -> dict:
    """Derive the interferer's matmul parameters for a sibling-load level.

    duty is the busy fraction of the interferer period. 'saturating' (duty=1.0)
    runs CONTINUOUSLY (period 0, back-to-back). light/medium fill `duty` of a fixed
    interferer_period_us with K reps sized from the reused per-scale slope. K is a
    granularity knob only when period=0.
    """
    ic = cfg["interferer"]
    levels = ic["sibling_load_levels"]
    if level not in levels:
        raise ValueError(f"unknown sibling-load level: {level} (have {list(levels)})")
    duty = float(levels[level]["duty"])
    if duty <= 0.0:
        return {"level": level, "duty": 0.0, "period_us": 0, "K": 0, "enabled": False}
    ktab = ktab if ktab is not None else load_source_ktable(cfg)
    slope = _scale_slope(ktab, scale) if ktab else None
    P_int = int(ic["interferer_period_us"])
    if duty >= 1.0:
        # saturating: continuous back-to-back (period 0). K is per-job granularity;
        # pick a moderate value from the slope (~one tight period of work) or 200.
        K = max(1, int(round((cfg["scales"]["tight"]["period_us"]) / slope))) if slope else 200
        return {"level": level, "duty": 1.0, "period_us": 0, "K": K, "enabled": True}
    busy_us = duty * P_int
    K = max(1, int(round(busy_us / slope))) if slope else max(1, int(round(busy_us / 5.0)))
    return {"level": level, "duty": duty, "period_us": P_int, "K": K, "enabled": True}


# --------------------------------------------------------------------------- #
# Naming helpers  (RFC1123-safe)
# --------------------------------------------------------------------------- #
def _u_int(u: float) -> int:
    return int(round(u * 100))


def cell_id(scale: str, u: float) -> str:
    return f"{scale}-U{u_label(u)}"


def rt_k8s_name(arm: str, scale: str, u: float) -> str:
    a = "phys" if arm == "physical" else "sib"
    return f"m3-{a}-{scale}-u{_u_int(u)}"


def interferer_k8s_name(arm: str, scale: str, u: float) -> str:
    return f"{rt_k8s_name(arm, scale, u)}-intf"


# --------------------------------------------------------------------------- #
# Cell grid
# --------------------------------------------------------------------------- #
def iter_cells(cfg: dict, arm: str, sibling_load: str | None = None,
               ktab: dict | None = None):
    """Yield every (scale, U) cell for an arm, tight first then soft.

    The RT reservation + K are IDENTICAL across arms (so C-inflation is isolated).
    For the sibling arm each cell carries the interferer spec for `sibling_load`
    (default from config).
    """
    ktab = ktab if ktab is not None else load_source_ktable(cfg)
    if arm not in cfg["arms"]:
        raise ValueError(f"unknown arm: {arm} (have {list(cfg['arms'])})")
    is_sibling = cfg["arms"][arm].get("interferer", False)
    level = sibling_load or (cfg["arms"][arm].get("default_sibling_load", "saturating")
                             if is_sibling else "off")
    for scale in ("tight", "soft"):
        if scale not in cfg["scales"]:
            continue
        sc = cfg["scales"][scale]
        for u in cfg["utilizations"]:
            q_us = derive_q_us(u, sc["period_us"])
            runtime, period = reservation_qp(cfg, q_us, sc["period_us"])
            intf = (interferer_spec(cfg, scale, level, ktab) if is_sibling
                    else {"level": "off", "duty": 0.0, "period_us": 0, "K": 0, "enabled": False})
            yield {
                "arm": arm,
                "arm_dir": cfg["arms"][arm]["dir"],
                "scale": scale,
                "scale_dir": sc["dir"],
                "period_ms": sc["period_ms"],
                "period_us": sc["period_us"],
                "u": u,
                "q_us": q_us,
                "m": cfg["cores_per_container"],
                "K": k_for_u(cfg, scale, u, ktab),
                "c_baseline_us": c_baseline_for_u(cfg, scale, u, ktab),
                "n_jobs": cfg["stopping_rule"]["n_jobs"],
                "warmup": cfg["stopping_rule"]["warmup_jobs"],
                "matrix_M": cfg["kernel"]["matrix_M"],
                "reservation_runtime": runtime,
                "reservation_period": period,
                "reservation_count": cfg["cores_per_container"],
                "sibling_load": intf["level"],
                "interferer": intf,
                "cell_id": cell_id(scale, u),
                "rt_name": rt_k8s_name(arm, scale, u),
                "interferer_name": interferer_k8s_name(arm, scale, u),
                "sample_rate_hz": cfg["sampling"]["rate_hz"][scale],
            }


# --------------------------------------------------------------------------- #
# CLI: dump the derived grid (sanity check; mirrors model2lib's __main__)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="dump Model 3 derived cell grid")
    ap.add_argument("--arm", choices=["physical", "sibling"], default="sibling")
    ap.add_argument("--sibling-load", default=None,
                    choices=["off", "light", "medium", "saturating"])
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    cfg = load_config(a.config)
    ktab = load_source_ktable(cfg)
    print(f"# config: {cfg['_config_path']}")
    print(f"# reused calibration: {source_table_path(cfg)} "
          f"({'FOUND' if ktab else 'MISSING -> K=None (dry-run only)'})")
    hdr = ["cell_id", "arm", "scale", "P_us", "U", "Q_us", "K", "C_baseline_us",
           "sibling_load", "intf_period_us", "intf_K", "N"]
    print("\t".join(hdr))
    for c in iter_cells(cfg, a.arm, a.sibling_load, ktab):
        print("\t".join(str(x) for x in [
            c["cell_id"], c["arm"], c["scale"], c["period_us"], c["u"], c["q_us"],
            c["K"], c["c_baseline_us"], c["sibling_load"],
            c["interferer"]["period_us"], c["interferer"]["K"], c["n_jobs"]]))
