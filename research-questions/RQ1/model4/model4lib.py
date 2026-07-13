#!/usr/bin/env python3
"""
model4lib — shared helpers for the Model 4 (IRQ-steering) harness.

Single place that loads config.yaml and derives everything that must stay DRY:
per-cell Q from U and P, the reused Model 1_1 calibration (K + C_baseline, read
from ../model1_1/calibration/k_table.json), the KubeDeadline reservation (Q,P,m),
the two IRQ ARMS' cell grids, the IRQ-source (iperf3) rate for a --irq-load level,
and directory/path/name templates.

NO recalibration happens in Model 4: IRQ interference is a DELAY (R - C) effect, so
C stays flat and Model 1_1's isolated-core K/C_baseline apply directly. The SAME K
is used for BOTH arms so the R-tail difference is a pure IRQ effect.

Every Model-4 script (renderer, orchestrator, analyzer, plots) imports from here so
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
    return ("%g" % u)


def scale_dir(cfg: dict, scale: str) -> str:
    return cfg["scales"][scale]["dir"]


def reservation_qp(cfg: dict, q_us: int, period_us: int):
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
    p = source_table_path(cfg)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _scale_slope(ktab: dict, scale: str):
    slopes = []
    for _, e in ktab.items():
        if e.get("scale") != scale:
            continue
        K = e.get("K"); c = e.get("median_C_us")
        if K and c and K > 0:
            slopes.append(c / K)
    return statistics.median(slopes) if slopes else None


def grid_entry(ktab: dict, scale: str, q_us: int):
    for _, e in ktab.items():
        if e.get("scale") == scale and e.get("Q_us") is not None:
            if abs(float(e["Q_us"]) - q_us) <= 0.5:
                return e
    return None


def k_for_u(cfg: dict, scale: str, u: float, ktab: dict | None = None):
    ktab = ktab if ktab is not None else load_source_ktable(cfg)
    period_us = cfg["scales"][scale]["period_us"]
    q_us = derive_q_us(u, period_us)
    e = grid_entry(ktab, scale, q_us)
    if e and e.get("K"):
        return int(e["K"])
    slope = _scale_slope(ktab, scale) if ktab else None
    if not slope or slope <= 0:
        return None
    min_reps = int(cfg["calibration"].get("min_reps", cfg["kernel"].get("min_reps", 1)))
    return max(min_reps, int(round(q_us / slope)))


def c_baseline_for_u(cfg: dict, scale: str, u: float, ktab: dict | None = None):
    ktab = ktab if ktab is not None else load_source_ktable(cfg)
    period_us = cfg["scales"][scale]["period_us"]
    e = grid_entry(ktab, scale, derive_q_us(u, period_us))
    return float(e["median_C_us"]) if e and e.get("median_C_us") is not None else None


# --------------------------------------------------------------------------- #
# IRQ-source (iperf3) rate for a --irq-load level
# --------------------------------------------------------------------------- #
def irq_source_spec(cfg: dict, level: str) -> dict:
    """Resolve the iperf3 generator parameters for an --irq-load level.

    Returns enabled flag + bitrate (iperf3 -b) + packet length. `off` disables the
    generator (ambient IRQ only). Requires irq_source.enabled globally.
    """
    isrc = cfg["irq_source"]
    levels = isrc["levels"]
    if level not in levels:
        raise ValueError(f"unknown irq-load level: {level} (have {list(levels)})")
    lv = levels[level]
    enabled = bool(isrc.get("enabled", True)) and lv.get("enabled", True) and level != "off"
    return {
        "level": level,
        "enabled": enabled,
        "bitrate": str(lv.get("bitrate", "0")),
        "packet_len": int(isrc.get("packet_len_bytes", 64)),
        "udp": bool(isrc.get("udp", True)),
        "duration_s": int(isrc.get("duration_s_per_burst", 3600)),
    }


# --------------------------------------------------------------------------- #
# Naming helpers  (RFC1123-safe)
# --------------------------------------------------------------------------- #
def _u_int(u: float) -> int:
    return int(round(u * 100))


def cell_id(scale: str, u: float) -> str:
    return f"{scale}-U{u_label(u)}"


def rt_k8s_name(arm: str, scale: str, u: float) -> str:
    return f"m4-{arm}-{scale}-u{_u_int(u)}"


# --------------------------------------------------------------------------- #
# Cell grid
# --------------------------------------------------------------------------- #
def iter_cells(cfg: dict, arm: str, ktab: dict | None = None):
    """Yield every (scale, U) cell for an arm, tight first then soft. The RT
    reservation + K are IDENTICAL across arms (so the R-tail diff is pure IRQ)."""
    ktab = ktab if ktab is not None else load_source_ktable(cfg)
    if arm not in cfg["arms"]:
        raise ValueError(f"unknown arm: {arm} (have {list(cfg['arms'])})")
    steer_onto_rt = cfg["arms"][arm].get("steer_onto_rt", False)
    for scale in ("tight", "soft"):
        if scale not in cfg["scales"]:
            continue
        sc = cfg["scales"][scale]
        for u in cfg["utilizations"]:
            q_us = derive_q_us(u, sc["period_us"])
            runtime, period = reservation_qp(cfg, q_us, sc["period_us"])
            yield {
                "arm": arm,
                "arm_dir": cfg["arms"][arm]["dir"],
                "steer_onto_rt": steer_onto_rt,
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
                "cell_id": cell_id(scale, u),
                "rt_name": rt_k8s_name(arm, scale, u),
                "sample_rate_hz": cfg["sampling"]["rate_hz"][scale],
            }


# --------------------------------------------------------------------------- #
# CLI: dump the derived grid (sanity check)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="dump Model 4 derived cell grid")
    ap.add_argument("--arm", choices=["off", "on"], default="on")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    cfg = load_config(a.config)
    ktab = load_source_ktable(cfg)
    print(f"# config: {cfg['_config_path']}")
    print(f"# reused calibration: {source_table_path(cfg)} "
          f"({'FOUND' if ktab else 'MISSING -> K=None (dry-run only)'})")
    hdr = ["cell_id", "arm", "scale", "P_us", "U", "Q_us", "K", "C_baseline_us",
           "steer_onto_rt", "N"]
    print("\t".join(hdr))
    for c in iter_cells(cfg, a.arm, ktab):
        print("\t".join(str(x) for x in [
            c["cell_id"], c["arm"], c["scale"], c["period_us"], c["u"], c["q_us"],
            c["K"], c["c_baseline_us"], c["steer_onto_rt"], c["n_jobs"]]))
