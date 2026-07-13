#!/usr/bin/env python3
"""
model2lib — shared helpers for the Model 2 (co-located contention) harness.

Single place that loads config.yaml and derives everything that must stay DRY:
per-cell/per-task Q from U and P, the reused Model 1_1 calibration (K derived by
linear scaling of ../model1_1/calibration/k_table.json, since C is linear in K),
the KubeDeadline reservation (Q,P,m), directory/path templates, and the two
variant cell grids (intra = task-vs-task, inter = server-vs-server).

NO recalibration happens in Model 2: per the user directive the workload
calibration is REUSED from Model 1_1. This module reads that table and, because
per-job compute C = slope * K for a fixed matrix M, converts ANY per-task /
per-container target compute into a K by  K = round(C_target / slope).

Every Model-2 script (renderer, orchestrator, parser, plots) imports from here so
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
# REUSED Model 1_1 calibration  (K derived by linear scaling; NO recalibration)
# --------------------------------------------------------------------------- #
def source_table_path(cfg: dict) -> Path:
    return (HERE / cfg["calibration"]["source_table"]).resolve()


def load_source_ktable(cfg: dict) -> dict:
    """Load Model 1_1's k_table.json (reused). Empty dict if missing (dry-run ok)."""
    p = source_table_path(cfg)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _scale_slope(ktab: dict, scale: str) -> float | None:
    """slope = median_C_us / K for the given scale (C is linear in K).

    Robust to per-cell noise: take the median of (median_C_us / K) over every
    calibrated cell of that scale. Returns None if the table has no such cells.
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


def k_for_target_C(cfg: dict, scale: str, C_target_us: float, ktab: dict | None = None):
    """Derive K so median compute C ~= C_target_us, by scaling the reused table.

    Prefers the EXACT table entry when C_target matches a grid cell's Q (most
    accurate); otherwise uses the per-scale linear slope. Returns None if the
    source table is unavailable (so callers can dry-run without calibration).
    """
    ktab = ktab if ktab is not None else load_source_ktable(cfg)
    if not ktab:
        return None
    min_reps = int(cfg["calibration"].get("min_reps", cfg["kernel"].get("min_reps", 1)))
    # exact grid hit?
    for _, e in ktab.items():
        if e.get("scale") == scale and e.get("Q_us") is not None:
            if abs(float(e["Q_us"]) - C_target_us) <= 0.5 and e.get("K"):
                return int(e["K"])
    slope = _scale_slope(ktab, scale)
    if not slope or slope <= 0:
        return None
    return max(min_reps, int(round(C_target_us / slope)))


def k_for_u(cfg: dict, scale: str, u: float, ktab: dict | None = None):
    """K for a full-utilisation-U task (target C = round(U*P))."""
    period_us = cfg["scales"][scale]["period_us"]
    return k_for_target_C(cfg, scale, derive_q_us(u, period_us), ktab)


# --------------------------------------------------------------------------- #
# Naming helpers  (RFC1123-safe)
# --------------------------------------------------------------------------- #
def _u_int(u: float) -> int:
    return int(round(u * 100))


def intra_cell_id(scale: str, u: float, k: int, split: str) -> str:
    return f"{scale}-U{u_label(u)}-k{k}-{split}"


def intra_k8s_name(scale: str, u: float, k: int, split: str) -> str:
    return f"m2-intra-{scale}-u{_u_int(u)}-k{k}-{split}"


def inter_cell_id(arm: str, target_u: float, n_nb: int, nb_unit: float,
                  oversub: bool = False) -> str:
    tag = "-oversub" if oversub else ""
    return f"{arm}-tU{u_label(target_u)}-nb{u_label(nb_unit)}x{n_nb}{tag}"


def inter_k8s_prefix(arm: str, target_u: float, n_nb: int) -> str:
    a = "tf" if arm == "target_fixed" else "nf"
    return f"m2-inter-{a}-tu{_u_int(target_u)}-nb{n_nb}"


# --------------------------------------------------------------------------- #
# Per-task utilisation splits (intra)
# --------------------------------------------------------------------------- #
def split_utilizations(cfg: dict, u: float, k: int, split: str):
    """Return the list of k per-task utilisations that sum to (approximately) U.

    equal  : U/k each.
    victim : task 0 = victim_utilization (fixed small); remaining (k-1) tasks share
             (U - victim_u) equally (the "greedy" tasks). k>=2 required.
    """
    if split == "equal" or k == 1:
        return [u / k] * k
    if split == "victim":
        vu = float(cfg["variants"]["intra"]["splits"]["victim"]["victim_utilization"])
        if k < 2:
            return [u]
        vu = min(vu, u)               # never exceed the container budget
        rest = max(0.0, u - vu) / (k - 1)
        return [vu] + [rest] * (k - 1)
    raise ValueError(f"unknown split: {split}")


# --------------------------------------------------------------------------- #
# Variant cell grids
# --------------------------------------------------------------------------- #
def iter_intra_cells(cfg: dict, ktab: dict | None = None):
    """Yield every intra (task-vs-task) cell, tight first then soft."""
    ktab = ktab if ktab is not None else load_source_ktable(cfg)
    v = cfg["variants"]["intra"]
    splits = []
    if v["splits"].get("equal", {}).get("enabled"):
        splits.append("equal")
    if v["splits"].get("victim", {}).get("enabled"):
        splits.append("victim")
    for scale in ("tight", "soft"):
        if scale not in cfg["scales"]:
            continue
        sc = cfg["scales"][scale]
        for u in v["container_utilizations"]:
            q_us = derive_q_us(u, sc["period_us"])
            runtime, period = reservation_qp(cfg, q_us, sc["period_us"])
            for k in v["k_tasks"]:
                for split in splits:
                    # victim split is only meaningful for k >= 2 (needs a victim +
                    # >=1 greedy); k=1 victim == k=1 equal, so skip the duplicate.
                    if split == "victim" and k < 2:
                        continue
                    task_us = split_utilizations(cfg, u, k, split)
                    task_C = [derive_q_us(tu, sc["period_us"]) for tu in task_us]
                    task_K = [k_for_target_C(cfg, scale, c, ktab) for c in task_C]
                    yield {
                        "variant": "intra",
                        "scale": scale,
                        "scale_dir": sc["dir"],
                        "period_ms": sc["period_ms"],
                        "period_us": sc["period_us"],
                        "u": u,
                        "q_us": q_us,
                        "m": cfg["cores_per_container"],
                        "k": k,
                        "split": split,
                        "task_utilizations": task_us,
                        "task_C_us": task_C,
                        "task_K": task_K,
                        "victim_index": (cfg["variants"]["intra"]["victim_task_index"]
                                         if split == "victim" else None),
                        "n_jobs": cfg["stopping_rule"]["n_jobs"],
                        "warmup": cfg["stopping_rule"]["warmup_jobs"],
                        "matrix_M": cfg["kernel"]["matrix_M"],
                        "reservation_runtime": runtime,
                        "reservation_period": period,
                        "reservation_count": cfg["cores_per_container"],
                        "cell_id": intra_cell_id(scale, u, k, split),
                        "cell_name": intra_k8s_name(scale, u, k, split),
                        "sample_rate_hz": cfg["sampling"]["rate_hz"][scale],
                    }


def _inter_cell(cfg, scale, sc, arm, target_u, n_nb, nb_unit, oversub, ktab):
    q_us = derive_q_us(target_u, sc["period_us"])
    runtime, period = reservation_qp(cfg, q_us, sc["period_us"])
    nb_q = derive_q_us(nb_unit, sc["period_us"])
    nb_runtime, nb_period = reservation_qp(cfg, nb_q, sc["period_us"])
    return {
        "variant": "inter",
        "arm": arm,
        "scale": scale,
        "scale_dir": sc["dir"],
        "period_ms": sc["period_ms"],
        "period_us": sc["period_us"],
        "target_u": target_u,
        "target_q_us": q_us,
        "target_K": k_for_u(cfg, scale, target_u, ktab),
        "m": cfg["cores_per_container"],
        "n_neighbours": n_nb,
        "neighbour_unit_u": nb_unit,
        "neighbour_q_us": nb_q,
        "neighbour_K": k_for_u(cfg, scale, nb_unit, ktab),
        "aggregate_neighbour_u": round(n_nb * nb_unit, 4),
        "oversubscribe": oversub,
        "n_jobs": cfg["stopping_rule"]["n_jobs"],
        "warmup": cfg["stopping_rule"]["warmup_jobs"],
        "matrix_M": cfg["kernel"]["matrix_M"],
        "target_reservation_runtime": runtime,
        "target_reservation_period": period,
        "neighbour_reservation_runtime": nb_runtime,
        "neighbour_reservation_period": nb_period,
        "reservation_count": cfg["cores_per_container"],
        "cell_id": inter_cell_id(arm, target_u, n_nb, nb_unit, oversub),
        "name_prefix": inter_k8s_prefix(arm, target_u, n_nb) + ("-os" if oversub else ""),
        "sample_rate_hz": cfg["sampling"]["rate_hz"][scale],
    }


def iter_inter_cells(cfg: dict, ktab: dict | None = None):
    """Yield every inter (server-vs-server) cell across both arms + oversub arm."""
    ktab = ktab if ktab is not None else load_source_ktable(cfg)
    v = cfg["variants"]["inter"]
    nb_unit = float(v["neighbour_unit_utilization"])
    for scale in ("tight", "soft"):
        if scale not in cfg["scales"]:
            continue
        sc = cfg["scales"][scale]
        # ARM A: target fixed, neighbour load swept
        ta = v.get("target_fixed", {})
        if ta.get("enabled"):
            tu = float(ta["target_utilization"])
            for n_nb in ta.get("neighbour_counts", []):
                yield _inter_cell(cfg, scale, sc, "target_fixed", tu, n_nb, nb_unit, False, ktab)
            for n_nb in ta.get("oversubscribe_neighbour_counts", []):
                yield _inter_cell(cfg, scale, sc, "target_fixed", tu, n_nb, nb_unit, True, ktab)
        # ARM B: neighbour fixed, target U swept
        tb = v.get("neighbour_fixed", {})
        if tb.get("enabled"):
            n_nb = int(tb["neighbour_count"])
            for tu in tb.get("target_utilizations", []):
                yield _inter_cell(cfg, scale, sc, "neighbour_fixed", tu, n_nb, nb_unit, False, ktab)


def iter_cells(cfg: dict, variant: str, ktab: dict | None = None):
    if variant == "intra":
        yield from iter_intra_cells(cfg, ktab)
    elif variant == "inter":
        yield from iter_inter_cells(cfg, ktab)
    else:
        raise ValueError(f"unknown variant: {variant}")


# --------------------------------------------------------------------------- #
# CLI: dump the derived grid (sanity check; mirrors model1lib's __main__)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="dump Model 2 derived cell grid")
    ap.add_argument("--variant", choices=["intra", "inter"], default="intra")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    cfg = load_config(a.config)
    ktab = load_source_ktable(cfg)
    print(f"# config: {cfg['_config_path']}")
    print(f"# reused calibration: {source_table_path(cfg)} "
          f"({'FOUND' if ktab else 'MISSING -> K=None (dry-run only)'})")
    if a.variant == "intra":
        hdr = ["cell_id", "scale", "P_us", "U", "Q_us", "k", "split",
               "task_U", "task_K", "N"]
        print("\t".join(hdr))
        for c in iter_intra_cells(cfg, ktab):
            print("\t".join(str(x) for x in [
                c["cell_id"], c["scale"], c["period_us"], c["u"], c["q_us"],
                c["k"], c["split"],
                ",".join(u_label(t) for t in c["task_utilizations"]),
                ",".join(str(k) for k in c["task_K"]), c["n_jobs"]]))
    else:
        hdr = ["cell_id", "arm", "scale", "P_us", "target_U", "target_Q", "target_K",
               "n_nb", "agg_nb_U", "nb_K", "oversub", "N"]
        print("\t".join(hdr))
        for c in iter_inter_cells(cfg, ktab):
            print("\t".join(str(x) for x in [
                c["cell_id"], c["arm"], c["scale"], c["period_us"], c["target_u"],
                c["target_q_us"], c["target_K"], c["n_neighbours"],
                c["aggregate_neighbour_u"], c["neighbour_K"], c["oversubscribe"],
                c["n_jobs"]]))
