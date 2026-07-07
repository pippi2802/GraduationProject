#!/usr/bin/env python3
"""
model1lib — shared helpers for the Model 1 harness.

Single place that loads config.yaml and derives everything that must stay DRY:
per-cell Q from U and P, the N_min/N_max map, directory/path templates, the
KubeDeadline reservation (Q, P, m) in the configured units, and the cell grid.

Every script (rtapp generator, orchestrator, parser, manifest renderer) imports
from here so a parameter change happens in exactly one file (config.yaml).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # fail loudly with a clear remedy
    sys.stderr.write("ERROR: PyYAML required. Install with: pip install pyyaml\n")
    raise

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.yaml"


# --------------------------------------------------------------------------- #
# Config loading
# --------------------------------------------------------------------------- #
def load_config(path: str | os.PathLike | None = None) -> dict:
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
    """Stable filesystem-safe label for a utilization, e.g. 0.95 -> '0.95'."""
    return ("%g" % u)


def cell_id(scale: str, u: float) -> str:
    return f"{scale}-U{u_label(u)}"


def k8s_name(scale: str, u: float) -> str:
    """RFC1123-safe object name (no dots/uppercase), e.g. 0.95 -> 'tight-u95'."""
    return f"{scale}-u{int(round(u * 100))}"


def scale_dir(cfg: dict, scale: str) -> str:
    return cfg["scales"][scale]["dir"]


def n_max_for(cfg: dict, scale: str, u: float) -> int:
    sr = cfg["stopping_rule"]
    n_max = sr["n_max_default"]
    for ov in sr.get("n_max_overrides", []):
        if ov["scale"] == scale and u in ov["utilizations"]:
            n_max = ov["n_max"]
    return n_max


def reservation_qp(cfg: dict, q_us: int, period_us: int) -> tuple[int, int]:
    """Return (runtime, period) in the configured reservation units."""
    units = cfg["kubedeadline_reservation_spec"]["units"]
    if units == "microseconds":
        return q_us, period_us
    if units == "milliseconds":
        # keep integer where possible; ms can be fractional so use int() guard
        return int(round(q_us / 1000)), int(round(period_us / 1000))
    if units == "nanoseconds":
        return q_us * 1000, period_us * 1000
    raise ValueError(f"unknown reservation units: {units}")


# --------------------------------------------------------------------------- #
# Cell grid
# --------------------------------------------------------------------------- #
def iter_cells(cfg: dict):
    """Yield every experiment cell as a dict, in deterministic sweep order.

    Order: tight scale first (tail is the story), ascending U; then soft scale.
    """
    order = ["tight", "soft"]
    for scale in order:
        sc = cfg["scales"][scale]
        for u in sc["utilizations"]:
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
                "n_min": cfg["stopping_rule"]["n_min"],
                "n_max": n_max_for(cfg, scale, u),
                "reservation_runtime": runtime,
                "reservation_period": period,
                # 'count' = number of cores m (paper: RtClaimParameters.count);
                # the driver's admission test auto-selects WHICH CPU(s).
                "reservation_count": cfg["cores_per_container"],
                "cell_id": cell_id(scale, u),
                "cell_name": k8s_name(scale, u),
                "sample_rate_hz": cfg["sampling"]["rate_hz"][scale],
            }


def canary_cell(cfg: dict) -> dict:
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
        "reservation_runtime": runtime,
        "reservation_period": period,
        # 'count' = number of cores m; driver auto-selects the CPU.
        "reservation_count": c["cores"],
        "cell_id": "canary",
        "cell_name": "model1-canary",
        "sample_rate_hz": cfg["sampling"]["rate_hz"][scale],
    }


def results_dir(cfg: dict, timeblock: str, scale_dir_: str, u: float) -> str:
    return cfg["results"]["path_template"].format(
        timeblock=timeblock, scale_dir=scale_dir_, u=u_label(u)
    )


if __name__ == "__main__":
    # quick self-check: print the derived grid
    cfg = load_config()
    print(f"# config: {cfg['_config_path']}")
    print(f"# reservation units: {cfg['kubedeadline_reservation_spec']['units']}")
    hdr = ["cell_id", "scale", "P_us", "U", "Q_us", "m",
           "runtime", "period", "N_min", "N_max", "hz"]
    print("\t".join(hdr))
    for c in iter_cells(cfg):
        print("\t".join(str(x) for x in [
            c["cell_id"], c["scale"], c["period_us"], c["u"], c["q_us"], c["m"],
            c["reservation_runtime"], c["reservation_period"],
            c["n_min"], c["n_max"], c["sample_rate_hz"],
        ]))
    cc = canary_cell(cfg)
    print("\t".join(str(x) for x in [
        cc["cell_id"], cc["scale"], cc["period_us"], cc["u"], cc["q_us"], cc["m"],
        cc["reservation_runtime"], cc["reservation_period"], "-", "-",
        cc["sample_rate_hz"],
    ]))
