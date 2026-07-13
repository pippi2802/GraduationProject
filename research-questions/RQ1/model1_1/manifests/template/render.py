#!/usr/bin/env python3
"""
Pure-Python renderer for Model 1_1 manifests (no envsubst / kubectl).

Substitutes the *.template.yaml files from values derived entirely from
config.yaml + the calibrated K table (via model1lib). Used both on-the-fly by
run_model1.py and to emit the committed per-U files (`render.py --all`).

A rendered cell is one multi-doc YAML stream:
  RtClaimParameters (Q,P,m) + ResourceClaimTemplate + Pod(matmul).

Usage:
  render.py --scale tight --u 0.9 [--timeblock LABEL]   # one cell -> stdout
  render.py --canary [--timeblock LABEL]                 # the canary -> stdout
  render.py --all [--timeblock LABEL]                     # write every rendered file
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent      # manifests/template
MANIFESTS = HERE.parent                       # manifests
ROOT = MANIFESTS.parent                       # model1_1
sys.path.insert(0, str(ROOT))
import model1lib as m1  # noqa: E402

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML required. pip install pyyaml\n")
    raise

RT_TEMPLATE = HERE / "rt-cell.template.yaml"
CANARY_TEMPLATE = HERE / "canary.template.yaml"
NAMESPACE = "model1-1"
CANARY_N_JOBS = 100000000   # effectively continuous


def _subst(text: str, mapping: dict) -> str:
    for k, v in mapping.items():
        text = text.replace("${%s}" % k, str(v))
    return text


def _label_kv(cfg: dict):
    key, _, val = cfg["node"]["node_label"].partition("=")
    return key, val


def _common(cfg: dict) -> dict:
    key, val = _label_kv(cfg)
    return {
        "NAMESPACE": NAMESPACE,
        "RES_CLASS": cfg["kubedeadline_reservation_spec"]["dra"]["resource_class_name"],
        "IMAGE": cfg["image"]["full_ref"],
        "PULL_POLICY": cfg["image"]["pull_policy"],
        "MATRIX_M": cfg["kernel"]["matrix_M"],
        "PRIORITY": cfg["kernel"]["fifo_priority"],
        "SEED": cfg["kernel"]["seed"],
        "NODE_LABEL_KEY": key,
        "NODE_LABEL_VAL": val,
    }


def _host_path(cfg: dict, timeblock: str, scale_dir: str, u: float) -> str:
    base = cfg["storage"]["host_path"]
    return f"{base}/{timeblock}/{scale_dir}/U{m1.u_label(u)}"


def render_cell(cfg: dict, scale: str, u: float, timeblock: str = "manual") -> str:
    K = m1.get_K(cfg, scale, u)
    if not K:
        raise SystemExit(f"ERROR: cell {m1.cell_id(scale, u)} not calibrated "
                         f"(no K). Run calibration first.")
    sc = cfg["scales"][scale]
    q_us = m1.derive_q_us(u, sc["period_us"])
    runtime, period = m1.reservation_qp(cfg, q_us, sc["period_us"])
    env = _common(cfg)
    env.update({
        "CELL_ID": m1.k8s_name(scale, u),
        "SCALE": scale,
        "RES_COUNT": cfg["cores_per_container"],
        "RES_RUNTIME": runtime,
        "RES_PERIOD": period,
        "K_REPS": K,
        "PERIOD_US": sc["period_us"],
        "N_JOBS": cfg["stopping_rule"]["n_jobs"],
        "WARMUP": cfg["stopping_rule"]["warmup_jobs"],
        "HOST_RESULTS_PATH": _host_path(cfg, timeblock, sc["dir"], u),
    })
    return _subst(RT_TEMPLATE.read_text(encoding="utf-8"), env).rstrip() + "\n"


def render_canary(cfg: dict, timeblock: str = "manual") -> str:
    c = m1.canary_cell(cfg)
    u = c["u"]
    K = m1.get_K(cfg, c["scale"], u)
    if not K:
        raise SystemExit("ERROR: canary cell not calibrated (no K). Calibrate first.")
    env = _common(cfg)
    env.update({
        "CELL_ID": c["cell_name"],
        "SCALE": c["scale"],
        "RES_COUNT": c["reservation_count"],
        "RES_RUNTIME": c["reservation_runtime"],
        "RES_PERIOD": c["reservation_period"],
        "K_REPS": K,
        "PERIOD_US": c["period_us"],
        "N_JOBS": CANARY_N_JOBS,
        "WARMUP": 0,
        "HOST_RESULTS_PATH": _host_path(cfg, timeblock, c["scale_dir"], u),
    })
    return _subst(CANARY_TEMPLATE.read_text(encoding="utf-8"), env).rstrip() + "\n"


def namespace_yaml() -> str:
    return yaml.safe_dump({"apiVersion": "v1", "kind": "Namespace",
                           "metadata": {"name": NAMESPACE}}, sort_keys=False)


def render_all(cfg: dict, timeblock: str = "manual"):
    written = []
    (MANIFESTS / "namespace.yaml").write_text(namespace_yaml(), encoding="utf-8")
    written.append(MANIFESTS / "namespace.yaml")
    ktab = m1.load_k_table(cfg)
    for scale, sc in cfg["scales"].items():
        outdir = MANIFESTS / sc["dir"]
        outdir.mkdir(parents=True, exist_ok=True)
        for u in cfg["utilizations"]:
            if not m1.get_K(cfg, scale, u, ktab):
                sys.stderr.write(f"skip {m1.cell_id(scale, u)} (not calibrated)\n")
                continue
            p = outdir / f"U{m1.u_label(u)}.yaml"
            p.write_text(render_cell(cfg, scale, u, timeblock), encoding="utf-8")
            written.append(p)
    if m1.get_K(cfg, cfg["canary"]["scale"], cfg["canary"]["utilization"], ktab):
        (MANIFESTS / "canary.yaml").write_text(render_canary(cfg, timeblock), encoding="utf-8")
        written.append(MANIFESTS / "canary.yaml")
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Render Model 1_1 manifests")
    ap.add_argument("--scale", choices=["tight", "soft"])
    ap.add_argument("--u", type=float)
    ap.add_argument("--canary", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--timeblock", default="manual")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    cfg = m1.load_config(a.config)
    if a.all:
        for p in render_all(cfg, a.timeblock):
            sys.stderr.write(f"wrote {p.relative_to(ROOT)}\n")
        return 0
    if a.canary:
        print(render_canary(cfg, a.timeblock)); return 0
    if a.scale is not None and a.u is not None:
        print(render_cell(cfg, a.scale, a.u, a.timeblock)); return 0
    ap.error("specify --all, --canary, or (--scale and --u)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
