#!/usr/bin/env python3
"""
Pure-Python renderer for Model 3 manifests (no envsubst / kubectl).

Substitutes the *.template.yaml files from values derived entirely from
config.yaml + the REUSED Model 1_1 K table (via model3lib). Used both on-the-fly
by run_model3.py and to emit the committed per-cell files (`render.py --all`).

A rendered RT cell is one multi-doc YAML stream:
  RtClaimParameters (Q,P,m=1) + ResourceClaimTemplate + Pod (one matmul task).

The interferer (sibling arm) is rendered SEPARATELY because its pinned logical CPU
(${SIBLING_CPU}) is only known at runtime (after the RT pod is Ready). `render.py
--all` emits committed interferer templates per (scale, load) with SIBLING_CPU left
as the literal placeholder <SIBLING_CPU>; run_model3.py fills it live.

Usage:
  render.py --arm physical --scale tight --u 0.8
  render.py --arm sibling  --scale tight --u 0.8 --sibling-load saturating
  render.py --interferer --scale tight --sibling-load saturating   # placeholder cpu
  render.py --all [--timeblock LABEL]     # write every rendered cell file
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent      # manifests/template
MANIFESTS = HERE.parent                       # manifests
ROOT = MANIFESTS.parent                       # model3
sys.path.insert(0, str(ROOT))
import model3lib as m3  # noqa: E402

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML required. pip install pyyaml\n")
    raise

RT_TEMPLATE = HERE / "rt-cell.template.yaml"
INTERFERER_TEMPLATE = MANIFESTS / "interferer" / "interferer.template.yaml"
NAMESPACE = "model3"
INTERFERER_N = 100000000          # interferer runs effectively continuously
SIBLING_CPU_PLACEHOLDER = "<SIBLING_CPU>"


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
        "NODE_LABEL_KEY": key,
        "NODE_LABEL_VAL": val,
    }


def _host_path(cfg, tb, arm_dir, scale_dir, u):
    base = cfg["storage"]["host_path"]
    return f"{base}/{tb}/{arm_dir}/{scale_dir}/U{m3.u_label(u)}"


# --------------------------------------------------------------------------- #
# RT cell
# --------------------------------------------------------------------------- #
def render_rt_cell(cfg, cell, timeblock="manual") -> str:
    if cell["K"] is None:
        raise SystemExit(f"ERROR: cell {cell['cell_id']} has undefined 'K' (reused "
                         f"Model 1_1 table missing?). Build ../model1_1 calibration first.")
    env = _common(cfg)
    env.update({
        "RT_NAME": cell["rt_name"],
        "ARM": cell["arm"],
        "CELL_ID": cell["cell_id"],
        "SCALE": cell["scale"],
        "MATRIX_M": cfg["kernel"]["matrix_M"],
        "PRIORITY": cfg["kernel"]["fifo_priority"],
        "SEED": cfg["kernel"]["seed"],
        "K_REPS": cell["K"],
        "RES_COUNT": cell["reservation_count"],
        "RES_RUNTIME": cell["reservation_runtime"],
        "RES_PERIOD": cell["reservation_period"],
        "PERIOD_US": cell["period_us"],
        "N_JOBS": cell["n_jobs"],
        "WARMUP": cell["warmup"],
        "HOST_RESULTS_PATH": _host_path(cfg, timeblock, cell["arm_dir"], cell["scale_dir"], cell["u"]),
    })
    return _subst(RT_TEMPLATE.read_text(encoding="utf-8"), env).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Interferer (sibling arm)
# --------------------------------------------------------------------------- #
def render_interferer(cfg, cell, timeblock="manual", sibling_cpu=SIBLING_CPU_PLACEHOLDER) -> str:
    intf = cell["interferer"]
    if not intf.get("enabled"):
        return ""   # off / physical arm -> no interferer
    env = _common(cfg)
    env.update({
        "OBJ_NAME": cell["interferer_name"],
        "ARM": cell["arm"],
        "CELL_ID": cell["cell_id"],
        "SCALE": cell["scale"],
        "SIBLING_LOAD": intf["level"],
        "SIBLING_CPU": sibling_cpu,
        "MATRIX_M": cfg["interferer"]["matrix_M"],
        "SEED": cfg["interferer"]["seed"],
        "K_REPS": intf["K"],
        "PERIOD_US": intf["period_us"],
        "N_JOBS": INTERFERER_N,
        "HOST_RESULTS_PATH": _host_path(cfg, timeblock, cell["arm_dir"], cell["scale_dir"], cell["u"]),
    })
    return _subst(INTERFERER_TEMPLATE.read_text(encoding="utf-8"), env).rstrip() + "\n"


# --------------------------------------------------------------------------- #
def namespace_yaml() -> str:
    return yaml.safe_dump({"apiVersion": "v1", "kind": "Namespace",
                           "metadata": {"name": NAMESPACE}}, sort_keys=False)


def render_all(cfg, timeblock="manual"):
    written = []
    (MANIFESTS / "namespace.yaml").write_text(namespace_yaml(), encoding="utf-8")
    written.append(MANIFESTS / "namespace.yaml")
    ktab = m3.load_source_ktable(cfg)
    # RT cells for both arms
    for arm in ("physical", "sibling"):
        for cell in m3.iter_cells(cfg, arm, None, ktab):
            if cell["K"] is None:
                sys.stderr.write(f"skip {arm} {cell['cell_id']} (no reused K)\n"); continue
            outdir = MANIFESTS / cell["arm_dir"] / cell["scale_dir"]
            outdir.mkdir(parents=True, exist_ok=True)
            p = outdir / f"U{m3.u_label(cell['u'])}.yaml"
            p.write_text(render_rt_cell(cfg, cell, timeblock), encoding="utf-8")
            written.append(p)
    # committed interferer templates: one per (scale, load level) with a placeholder cpu
    outdir = MANIFESTS / "interferer"
    for scale in ("tight", "soft"):
        for level in cfg["interferer"]["sibling_load_levels"]:
            if level == "off":
                continue
            # borrow the dose-response U just to build a representative interferer doc
            u = cfg["interferer"]["dose_response_utilization"]
            cell = next((c for c in m3.iter_cells(cfg, "sibling", level, ktab)
                         if c["scale"] == scale and c["u"] == u), None)
            if not cell:
                continue
            doc = render_interferer(cfg, cell, timeblock, SIBLING_CPU_PLACEHOLDER)
            if not doc:
                continue
            p = outdir / f"{scale}-{level}.yaml"
            p.write_text(doc, encoding="utf-8")
            written.append(p)
    return written


def _find_cell(cfg, arm, scale, u, sibling_load, ktab):
    for c in m3.iter_cells(cfg, arm, sibling_load, ktab):
        if c["scale"] == scale and c["u"] == u:
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Render Model 3 manifests")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--timeblock", default="manual")
    ap.add_argument("--config", default=None)
    ap.add_argument("--arm", choices=["physical", "sibling"])
    ap.add_argument("--scale", choices=["tight", "soft"])
    ap.add_argument("--u", type=float)
    ap.add_argument("--sibling-load", default=None,
                    choices=["off", "light", "medium", "saturating"])
    ap.add_argument("--interferer", action="store_true",
                    help="render only the interferer doc (placeholder sibling cpu)")
    a = ap.parse_args()
    cfg = m3.load_config(a.config)
    ktab = m3.load_source_ktable(cfg)
    if a.all:
        for p in render_all(cfg, a.timeblock):
            sys.stderr.write(f"wrote {p.relative_to(ROOT)}\n")
        return 0
    if a.interferer:
        cell = _find_cell(cfg, "sibling", a.scale, a.u, a.sibling_load, ktab)
        if not cell:
            ap.error("no matching sibling cell in the config grid")
        print(render_interferer(cfg, cell, a.timeblock)); return 0
    if a.arm:
        cell = _find_cell(cfg, a.arm, a.scale, a.u, a.sibling_load, ktab)
        if not cell:
            ap.error("no matching cell in the config grid")
        print(render_rt_cell(cfg, cell, a.timeblock)); return 0
    ap.error("specify --all, --arm ARM --scale S --u U, or --interferer --scale S --u U --sibling-load L")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
