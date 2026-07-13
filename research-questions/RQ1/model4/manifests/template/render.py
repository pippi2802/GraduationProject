#!/usr/bin/env python3
"""
Pure-Python renderer for Model 4 manifests (no envsubst / kubectl).

Substitutes the *.template.yaml files from values derived entirely from config.yaml
+ the REUSED Model 1_1 K table (via model4lib). Used both on-the-fly by
run_model4.py and to emit the committed per-cell files (`render.py --all`).

A rendered RT cell is one multi-doc YAML stream:
  RtClaimParameters (Q,P,m=1) + ResourceClaimTemplate + Pod (one matmul task).

The IRQ source (optional) is rendered separately because its ${SERVER_IP} is only
known at runtime (the server pod's hostIP). `render.py --all` emits a committed
per-load copy with the literal placeholder <SERVER_IP>.

Usage:
  render.py --arm on  --scale tight --u 0.8
  render.py --irq-source --irq-load medium        # placeholder server ip
  render.py --all [--timeblock LABEL]             # write every rendered cell file
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent      # manifests/template
MANIFESTS = HERE.parent                       # manifests
ROOT = MANIFESTS.parent                       # model4
sys.path.insert(0, str(ROOT))
import model4lib as m4  # noqa: E402

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML required. pip install pyyaml\n")
    raise

RT_TEMPLATE = HERE / "rt-cell.template.yaml"
IRQ_SOURCE_TEMPLATE = MANIFESTS / "irq-source" / "irq-source.template.yaml"
NAMESPACE = "model4"
SERVER_IP_PLACEHOLDER = "<SERVER_IP>"
IRQ_PORT = 5201


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
    return f"{base}/{tb}/{arm_dir}/{scale_dir}/U{m4.u_label(u)}"


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
# IRQ source (optional generator)
# --------------------------------------------------------------------------- #
def irq_source_names(irq_load: str) -> dict:
    return {"server": f"m4-irqsrc-{irq_load}-server",
            "client": f"m4-irqsrc-{irq_load}-client"}


def render_irq_source(cfg, irq_load: str, server_ip=SERVER_IP_PLACEHOLDER) -> str:
    spec = m4.irq_source_spec(cfg, irq_load)
    if not spec["enabled"]:
        return ""
    isrc = cfg["irq_source"]
    key, val = _label_kv(cfg)
    names = irq_source_names(irq_load)
    env = {
        "NAMESPACE": NAMESPACE,
        "NODE_LABEL_KEY": key,
        "NODE_LABEL_VAL": val,
        "SERVER_NAME": names["server"],
        "CLIENT_NAME": names["client"],
        "IRQ_SOURCE_IMAGE": isrc["image"],
        "SERVER_HOST_NETWORK": str(bool(isrc.get("server_host_network", True))).lower(),
        "IRQ_LOAD": irq_load,
        "PORT": IRQ_PORT,
        "BITRATE": spec["bitrate"],
        "PACKET_LEN": spec["packet_len"],
        "DURATION_S": spec["duration_s"],
        "SERVER_IP": server_ip,
    }
    return _subst(IRQ_SOURCE_TEMPLATE.read_text(encoding="utf-8"), env).rstrip() + "\n"


# --------------------------------------------------------------------------- #
def namespace_yaml() -> str:
    return yaml.safe_dump({"apiVersion": "v1", "kind": "Namespace",
                           "metadata": {"name": NAMESPACE}}, sort_keys=False)


def render_all(cfg, timeblock="manual"):
    written = []
    (MANIFESTS / "namespace.yaml").write_text(namespace_yaml(), encoding="utf-8")
    written.append(MANIFESTS / "namespace.yaml")
    ktab = m4.load_source_ktable(cfg)
    for arm in ("off", "on"):
        for cell in m4.iter_cells(cfg, arm, ktab):
            if cell["K"] is None:
                sys.stderr.write(f"skip {arm} {cell['cell_id']} (no reused K)\n"); continue
            outdir = MANIFESTS / cell["arm_dir"] / cell["scale_dir"]
            outdir.mkdir(parents=True, exist_ok=True)
            p = outdir / f"U{m4.u_label(cell['u'])}.yaml"
            p.write_text(render_rt_cell(cfg, cell, timeblock), encoding="utf-8")
            written.append(p)
    # committed IRQ-source per load level (placeholder server ip)
    outdir = MANIFESTS / "irq-source"
    for level in cfg["irq_source"]["levels"]:
        doc = render_irq_source(cfg, level, SERVER_IP_PLACEHOLDER)
        if not doc:
            continue
        p = outdir / f"{level}.yaml"
        p.write_text(doc, encoding="utf-8")
        written.append(p)
    return written


def _find_cell(cfg, arm, scale, u, ktab):
    for c in m4.iter_cells(cfg, arm, ktab):
        if c["scale"] == scale and c["u"] == u:
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Render Model 4 manifests")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--timeblock", default="manual")
    ap.add_argument("--config", default=None)
    ap.add_argument("--arm", choices=["off", "on"])
    ap.add_argument("--scale", choices=["tight", "soft"])
    ap.add_argument("--u", type=float)
    ap.add_argument("--irq-source", action="store_true")
    ap.add_argument("--irq-load", default=None, choices=["off", "light", "medium", "heavy"])
    a = ap.parse_args()
    cfg = m4.load_config(a.config)
    ktab = m4.load_source_ktable(cfg)
    if a.all:
        for p in render_all(cfg, a.timeblock):
            sys.stderr.write(f"wrote {p.relative_to(ROOT)}\n")
        return 0
    if a.irq_source:
        print(render_irq_source(cfg, a.irq_load or cfg["irq_source"]["default_irq_load"]))
        return 0
    if a.arm:
        c = _find_cell(cfg, a.arm, a.scale, a.u, ktab)
        if not c:
            ap.error("no matching cell in the config grid")
        print(render_rt_cell(cfg, c, a.timeblock)); return 0
    ap.error("specify --all, --arm ARM --scale S --u U, or --irq-source --irq-load L")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
