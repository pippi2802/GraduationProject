#!/usr/bin/env python3
"""
model1lib — shared helpers for the Model 1_1 harness.

Single place that loads config.yaml and derives everything that must stay DRY:
per-cell Q from U and P, the calibrated K per cell, directory/path templates, the
KubeDeadline reservation (Q, P, m) in the configured units, and the cell grid.

Every script (calibrator, manifest renderer, orchestrator, parser, plots) imports
from here so a parameter change happens in exactly one file (config.yaml).
"""
from __future__ import annotations

import json
import os
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


def cell_id(scale: str, u: float) -> str:
    return f"{scale}-U{u_label(u)}"


def k8s_name(scale: str, u: float) -> str:
    """RFC1123-safe object name, e.g. 0.94 -> 'tight-u94'."""
    return f"{scale}-u{int(round(u * 100))}"


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
# Calibration table  (K per cell)
# --------------------------------------------------------------------------- #
def k_table_path(cfg: dict) -> Path:
    return HERE / cfg["calibration"]["table_file"]


def load_k_table(cfg: dict) -> dict:
    """{ 'tight-U0.2': {'K': 1234, 'median_C_us': 2001, 'cv': 0.012, 'M': 48}, ... }"""
    p = k_table_path(cfg)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def get_K(cfg: dict, scale: str, u: float, ktab: dict | None = None):
    """Calibrated K for a cell, or None if not calibrated yet."""
    ktab = ktab if ktab is not None else load_k_table(cfg)
    entry = ktab.get(cell_id(scale, u))
    return entry.get("K") if entry else None


# --------------------------------------------------------------------------- #
# Cell grid
# --------------------------------------------------------------------------- #
def iter_cells(cfg: dict, ktab: dict | None = None):
    """Yield every experiment cell as a dict, tight first then soft, ascending U."""
    ktab = ktab if ktab is not None else load_k_table(cfg)
    order = ["tight", "soft"]
    for scale in order:
        if scale not in cfg["scales"]:
            continue
        sc = cfg["scales"][scale]
        for u in cfg["utilizations"]:
            q_us = derive_q_us(u, sc["period_us"])
            runtime, period = reservation_qp(cfg, q_us, sc["period_us"])
            yield {
                "scale": scale,
                "scale_dir": sc["dir"],
                "period_ms": sc["period_ms"],
                "period_us": sc["period_us"],
                "u": u,
                "q_us": q_us,
                "m": cfg["cores_per_container"],
                "n_jobs": cfg["stopping_rule"]["n_jobs"],
                "warmup": cfg["stopping_rule"]["warmup_jobs"],
                "K": get_K(cfg, scale, u, ktab),
                "matrix_M": cfg["kernel"]["matrix_M"],
                "reservation_runtime": runtime,
                "reservation_period": period,
                "reservation_count": cfg["cores_per_container"],
                "cell_id": cell_id(scale, u),
                "cell_name": k8s_name(scale, u),
                "sample_rate_hz": cfg["sampling"]["rate_hz"][scale],
            }


def canary_cell(cfg: dict, ktab: dict | None = None) -> dict:
    c = cfg["canary"]
    scale = c["scale"]
    sc = cfg["scales"][scale]
    q_us = derive_q_us(c["utilization"], sc["period_us"])
    runtime, period = reservation_qp(cfg, q_us, sc["period_us"])
    return {
        "scale": scale,
        "scale_dir": sc["dir"],
        "period_ms": sc["period_ms"],
        "period_us": sc["period_us"],
        "u": c["utilization"],
        "q_us": q_us,
        "m": c["cores"],
        "K": get_K(cfg, scale, c["utilization"], ktab),
        "matrix_M": cfg["kernel"]["matrix_M"],
        "reservation_runtime": runtime,
        "reservation_period": period,
        "reservation_count": c["cores"],
        "cell_id": "canary",
        "cell_name": "model1-1-canary",
        "sample_rate_hz": cfg["sampling"]["rate_hz"][scale],
    }


def results_dir(cfg: dict, timeblock: str, scale_dir_: str, u: float) -> str:
    return cfg["results"]["path_template"].format(
        timeblock=timeblock, scale_dir=scale_dir_, u=u_label(u))


if __name__ == "__main__":
    cfg = load_config()
    ktab = load_k_table(cfg)
    print(f"# config: {cfg['_config_path']}")
    print(f"# reservation units: {cfg['kubedeadline_reservation_spec']['units']}")
    hdr = ["cell_id", "scale", "P_us", "U", "Q_us", "m", "K", "M",
           "runtime", "period", "N", "warmup", "hz"]
    print("\t".join(hdr))
    for c in iter_cells(cfg, ktab):
        print("\t".join(str(x) for x in [
            c["cell_id"], c["scale"], c["period_us"], c["u"], c["q_us"], c["m"],
            c["K"], c["matrix_M"], c["reservation_runtime"], c["reservation_period"],
            c["n_jobs"], c["warmup"], c["sample_rate_hz"]]))
