#!/usr/bin/env python3
"""
Pure-Python renderer for Model 1 Kubernetes manifests.

This is the SINGLE DRY source-of-truth renderer: it substitutes the *.template.yaml
files in this directory with values derived entirely from config.yaml (via
model1lib) and the rt-app JSON (via rtapp/generate_rtapp.py). It needs NO
`envsubst` and NO `kubectl` (cross-platform: Windows/macOS/Linux), so it can both
(a) render on-the-fly for the orchestrator and (b) emit the committed per-U files.

A rendered cell is one complete multi-doc YAML stream:
  RtClaimParameters (Q,P,m)  +  ResourceClaimTemplate  +  Pod  +  rt-app ConfigMap

Usage:
  render.py --scale tight --u 0.95 [--timeblock LABEL]     # one RT cell -> stdout
  render.py --canary [--timeblock LABEL]                   # the canary   -> stdout
  render.py --all [--timeblock LABEL]                       # write every file:
        manifests/namespace.yaml
        manifests/<scale-dir>/U<U>.yaml   (all cells)
        manifests/canary.yaml
  (default --timeblock is 'manual' so committed files are directly kubectl-apply-able.)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent      # manifests/template
MANIFESTS = HERE.parent                       # manifests
ROOT = MANIFESTS.parent                       # model1
sys.path.insert(0, str(ROOT))
import model1lib as m1  # noqa: E402
sys.path.insert(0, str(ROOT / "rtapp"))
import generate_rtapp  # noqa: E402

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML required. Install with: pip install pyyaml\n")
    raise

RT_TEMPLATE = HERE / "rt-cell.template.yaml"
CANARY_TEMPLATE = HERE / "canary.template.yaml"
NAMESPACE = "model1"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _subst(text: str, mapping: dict) -> str:
    """Replace ${VAR} placeholders. Runtime shell vars in the entrypoint (e.g.
    $RT_CPUSET, written without braces) are left untouched on purpose."""
    for k, v in mapping.items():
        text = text.replace("${%s}" % k, str(v))
    return text


def _configmap_yaml(name: str, rtapp_json_text: str) -> str:
    """Emulate `kubectl create configmap NAME -n model1 --from-file=rtapp.json=... -o yaml`."""
    doc = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name, "namespace": NAMESPACE},
        "data": {"rtapp.json": rtapp_json_text},
    }
    return yaml.safe_dump(doc, default_flow_style=False, sort_keys=False)


def _rt_env(cfg: dict, scale: str, u: float, timeblock: str) -> tuple[dict, str]:
    sc = cfg["scales"][scale]
    q_us = m1.derive_q_us(u, sc["period_us"])
    runtime, period = m1.reservation_qp(cfg, q_us, sc["period_us"])
    res = cfg["kubedeadline_reservation_spec"]
    img = cfg["image"]
    name = m1.k8s_name(scale, u)
    host_path = f"{cfg['results']['host_path']}/{timeblock}/{sc['dir']}/U{m1.u_label(u)}"
    env = {
        "CELL_ID": name,
        "NAMESPACE": NAMESPACE,
        "RES_RUNTIME": runtime,
        "RES_PERIOD": period,
        "RES_COUNT": cfg["cores_per_container"],
        "RES_CLASS": res["dra"]["resource_class_name"],
        "SCALE": scale,
        "BASE_IMAGE": img["base_image"],
        "RTAPP_PKG": img["rtapp_apt_package"],
        "PULL_POLICY": img["pull_policy"],
        "HOST_RESULTS_PATH": host_path,
    }
    return env, name


def _canary_env(cfg: dict, timeblock: str) -> tuple[dict, str, str, float]:
    c = m1.canary_cell(cfg)
    scale = c["scale"]
    u = c["u"]
    img = cfg["image"]
    res = cfg["kubedeadline_reservation_spec"]
    name = c["cell_name"]  # 'model1-canary'
    host_path = f"{cfg['results']['host_path']}/{timeblock}/{c['scale_dir']}/U{m1.u_label(u)}"
    env = {
        "CELL_ID": name,
        "NAMESPACE": NAMESPACE,
        "RES_RUNTIME": c["reservation_runtime"],
        "RES_PERIOD": c["reservation_period"],
        "RES_COUNT": c["reservation_count"],
        "RES_CLASS": res["dra"]["resource_class_name"],
        "SCALE": scale,
        "BASE_IMAGE": img["base_image"],
        "RTAPP_PKG": img["rtapp_apt_package"],
        "PULL_POLICY": img["pull_policy"],
        "HOST_RESULTS_PATH": host_path,
    }
    return env, name, scale, u


# --------------------------------------------------------------------------- #
# public render functions (also imported by run_model1.py)
# --------------------------------------------------------------------------- #
def render_cell(cfg: dict, scale: str, u: float, timeblock: str = "manual") -> str:
    env, name = _rt_env(cfg, scale, u, timeblock)
    body = _subst(RT_TEMPLATE.read_text(encoding="utf-8"), env)
    rt_json = json.dumps(generate_rtapp.build(cfg, scale, u, None, "/results"), indent=2)
    cm = _configmap_yaml(name + "-rtapp", rt_json)
    return body.rstrip() + "\n---\n" + cm


def render_canary(cfg: dict, timeblock: str = "manual") -> str:
    env, name, scale, u = _canary_env(cfg, timeblock)
    body = _subst(CANARY_TEMPLATE.read_text(encoding="utf-8"), env)
    rt_json = json.dumps(generate_rtapp.build(cfg, scale, u, None, "/results"), indent=2)
    cm = _configmap_yaml(name + "-rtapp", rt_json)
    return body.rstrip() + "\n---\n" + cm


def namespace_yaml() -> str:
    doc = {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": NAMESPACE}}
    return yaml.safe_dump(doc, default_flow_style=False, sort_keys=False)


def render_all(cfg: dict, timeblock: str = "manual") -> list[Path]:
    written = []
    (MANIFESTS / "namespace.yaml").write_text(namespace_yaml(), encoding="utf-8")
    written.append(MANIFESTS / "namespace.yaml")
    for scale, sc in cfg["scales"].items():
        outdir = MANIFESTS / sc["dir"]
        outdir.mkdir(parents=True, exist_ok=True)
        for u in sc["utilizations"]:
            p = outdir / f"U{m1.u_label(u)}.yaml"
            p.write_text(render_cell(cfg, scale, u, timeblock) + "\n", encoding="utf-8")
            written.append(p)
    (MANIFESTS / "canary.yaml").write_text(render_canary(cfg, timeblock) + "\n", encoding="utf-8")
    written.append(MANIFESTS / "canary.yaml")
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Render Model 1 manifests (pure Python)")
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
        print(render_canary(cfg, a.timeblock))
        return 0
    if a.scale is not None and a.u is not None:
        print(render_cell(cfg, a.scale, a.u, a.timeblock))
        return 0
    ap.error("specify --all, --canary, or (--scale and --u)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
