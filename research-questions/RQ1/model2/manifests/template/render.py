#!/usr/bin/env python3
"""
Pure-Python renderer for Model 2 manifests (no envsubst / kubectl).

Substitutes the *.template.yaml files from values derived entirely from
config.yaml + the REUSED Model 1_1 K table (via model2lib). Used both on-the-fly
by run_model2.py and to emit the committed per-cell files (`render.py --all`).

A rendered INTRA cell is one multi-doc YAML stream:
  RtClaimParameters (Q,P,m=1) + ResourceClaimTemplate + Pod (k matmul tasks).

A rendered INTER cell is SEVERAL stacked streams (target + n neighbours), each:
  RtClaimParameters (Q_i,P,m=1) + ResourceClaimTemplate + Pod (one matmul task).

Usage:
  render.py --variant intra --scale tight --u 0.8 --k 4 --split equal
  render.py --variant inter --arm target_fixed --scale tight --target-u 0.4 --n-nb 4
  render.py --all [--timeblock LABEL]     # write every rendered cell file
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent      # manifests/template
MANIFESTS = HERE.parent                       # manifests
ROOT = MANIFESTS.parent                       # model2
sys.path.insert(0, str(ROOT))
import model2lib as m2  # noqa: E402

try:
    import yaml
except ImportError:
    sys.stderr.write("ERROR: PyYAML required. pip install pyyaml\n")
    raise

INTRA_TEMPLATE = HERE / "intra-cell.template.yaml"
INTER_TEMPLATE = HERE / "inter-reservation.template.yaml"
NAMESPACE = "model2"
INTER_NEIGHBOUR_N = 100000000   # neighbours run effectively continuously
LAUNCH_INDENT = " " * 10        # matches the YAML block-scalar indent


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


def _intra_host_path(cfg, tb, scale_dir, cell_id):
    base = cfg["storage"]["host_path"]
    return f"{base}/{tb}/intra/{scale_dir}/{cell_id}"


def _inter_host_path(cfg, tb, scale_dir, arm, cell_id):
    base = cfg["storage"]["host_path"]
    return f"{base}/{tb}/inter/{scale_dir}/{arm}/{cell_id}"


# --------------------------------------------------------------------------- #
# INTRA
# --------------------------------------------------------------------------- #
def _task_launch_block(cfg, cell) -> str:
    M = cfg["kernel"]["matrix_M"]
    P = cell["period_us"]
    N = cell["n_jobs"]
    W = cell["warmup"]
    pri = cfg["kernel"]["fifo_priority"]
    seed = cfg["kernel"]["seed"]
    lines = []
    for i, K in enumerate(cell["task_K"]):
        role = ""
        if cell.get("victim_index") is not None:
            role = "  # victim" if i == cell["victim_index"] else "  # greedy"
        lines.append(
            f'{LAUNCH_INDENT}$PIN /usr/local/bin/matmul '
            f'--M {M} --K {K} --period-us {P} --n-jobs {N} --warmup {W} '
            f'--priority {pri} --cpu env --seed {seed} '
            f'--logfile /results/task{i}.csv &{role}')
    return "\n".join(lines)


def render_intra_cell(cfg, cell, timeblock="manual") -> str:
    if any(k is None for k in cell["task_K"]):
        raise SystemExit(f"ERROR: intra cell {cell['cell_id']} has undefined 'K' (reused "
                         f"Model 1_1 table missing?). Build ../model1_1 calibration first.")
    env = _common(cfg)
    env.update({
        "CELL_ID": cell["cell_name"],
        "SCALE": cell["scale"],
        "SPLIT": cell["split"],
        "K_TASKS": cell["k"],
        "RES_COUNT": cell["reservation_count"],
        "RES_RUNTIME": cell["reservation_runtime"],
        "RES_PERIOD": cell["reservation_period"],
        "PERIOD_US": cell["period_us"],
        "N_JOBS": cell["n_jobs"],
        "HOST_RESULTS_PATH": _intra_host_path(cfg, timeblock, cell["scale_dir"], cell["cell_id"]),
        "TASK_LAUNCH_BLOCK": _task_launch_block(cfg, cell),
    })
    return _subst(INTRA_TEMPLATE.read_text(encoding="utf-8"), env).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# INTER
# --------------------------------------------------------------------------- #
def inter_object_names(cell) -> dict:
    """{'target': name, 'neighbours': [names...]} for a rendered inter cell."""
    pfx = cell["name_prefix"]
    return {"target": f"{pfx}-tgt",
            "neighbours": [f"{pfx}-nb{i}" for i in range(cell["n_neighbours"])]}


def _render_inter_reservation(cfg, cell, obj_name, role, logfile, res_runtime,
                              res_period, k_reps, n_jobs, warmup, host_path) -> str:
    env = _common(cfg)
    env.update({
        "OBJ_NAME": obj_name,
        "ROLE": role,
        "ARM": cell["arm"],
        "CELL_ID": cell["cell_id"],
        "SCALE": cell["scale"],
        "RES_COUNT": cell["reservation_count"],
        "RES_RUNTIME": res_runtime,
        "RES_PERIOD": res_period,
        "K_REPS": k_reps,
        "PERIOD_US": cell["period_us"],
        "N_JOBS": n_jobs,
        "WARMUP": warmup,
        "LOGFILE": logfile,
        "HOST_RESULTS_PATH": host_path,
    })
    return _subst(INTER_TEMPLATE.read_text(encoding="utf-8"), env).rstrip() + "\n"


def render_inter_cell(cfg, cell, timeblock="manual") -> str:
    if cell["target_K"] is None or (cell["n_neighbours"] and cell["neighbour_K"] is None):
        raise SystemExit(f"ERROR: inter cell {cell['cell_id']} has undefined 'K' (reused "
                         f"Model 1_1 table missing?). Build ../model1_1 calibration first.")
    names = inter_object_names(cell)
    hp = _inter_host_path(cfg, timeblock, cell["scale_dir"], cell["arm"], cell["cell_id"])
    docs = [_render_inter_reservation(
        cfg, cell, names["target"], "target", "target.csv",
        cell["target_reservation_runtime"], cell["target_reservation_period"],
        cell["target_K"], cell["n_jobs"], cell["warmup"], hp)]
    for i, nb in enumerate(names["neighbours"]):
        docs.append(_render_inter_reservation(
            cfg, cell, nb, "neighbour", f"neighbour{i}.csv",
            cell["neighbour_reservation_runtime"], cell["neighbour_reservation_period"],
            cell["neighbour_K"], INTER_NEIGHBOUR_N, 0, hp))
    return ("---\n").join(d for d in docs)


# --------------------------------------------------------------------------- #
def namespace_yaml() -> str:
    return yaml.safe_dump({"apiVersion": "v1", "kind": "Namespace",
                           "metadata": {"name": NAMESPACE}}, sort_keys=False)


def render_all(cfg, timeblock="manual"):
    written = []
    (MANIFESTS / "namespace.yaml").write_text(namespace_yaml(), encoding="utf-8")
    written.append(MANIFESTS / "namespace.yaml")
    ktab = m2.load_source_ktable(cfg)
    # intra
    for cell in m2.iter_intra_cells(cfg, ktab):
        if any(k is None for k in cell["task_K"]):
            sys.stderr.write(f"skip intra {cell['cell_id']} (no reused K)\n"); continue
        outdir = MANIFESTS / "intra" / cell["scale_dir"]
        outdir.mkdir(parents=True, exist_ok=True)
        p = outdir / f"{cell['cell_id']}.yaml"
        p.write_text(render_intra_cell(cfg, cell, timeblock), encoding="utf-8")
        written.append(p)
    # inter
    for cell in m2.iter_inter_cells(cfg, ktab):
        if cell["target_K"] is None:
            sys.stderr.write(f"skip inter {cell['cell_id']} (no reused K)\n"); continue
        outdir = MANIFESTS / "inter" / cell["scale_dir"] / cell["arm"]
        outdir.mkdir(parents=True, exist_ok=True)
        p = outdir / f"{cell['cell_id']}.yaml"
        p.write_text(render_inter_cell(cfg, cell, timeblock), encoding="utf-8")
        written.append(p)
    return written


def _find_intra(cfg, scale, u, k, split, ktab):
    for c in m2.iter_intra_cells(cfg, ktab):
        if (c["scale"] == scale and c["u"] == u and c["k"] == k and c["split"] == split):
            return c
    return None


def _find_inter(cfg, arm, scale, target_u, n_nb, ktab):
    for c in m2.iter_inter_cells(cfg, ktab):
        if (c["arm"] == arm and c["scale"] == scale and c["target_u"] == target_u
                and c["n_neighbours"] == n_nb):
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Render Model 2 manifests")
    ap.add_argument("--variant", choices=["intra", "inter"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--timeblock", default="manual")
    ap.add_argument("--config", default=None)
    # intra
    ap.add_argument("--scale", choices=["tight", "soft"])
    ap.add_argument("--u", type=float)
    ap.add_argument("--k", type=int)
    ap.add_argument("--split", choices=["equal", "victim"])
    # inter
    ap.add_argument("--arm", choices=["target_fixed", "neighbour_fixed"])
    ap.add_argument("--target-u", type=float)
    ap.add_argument("--n-nb", type=int)
    a = ap.parse_args()
    cfg = m2.load_config(a.config)
    ktab = m2.load_source_ktable(cfg)
    if a.all:
        for p in render_all(cfg, a.timeblock):
            sys.stderr.write(f"wrote {p.relative_to(ROOT)}\n")
        return 0
    if a.variant == "intra":
        c = _find_intra(cfg, a.scale, a.u, a.k, a.split or "equal", ktab)
        if not c:
            ap.error("no matching intra cell in the config grid")
        print(render_intra_cell(cfg, c, a.timeblock)); return 0
    if a.variant == "inter":
        c = _find_inter(cfg, a.arm or "target_fixed", a.scale, a.target_u, a.n_nb, ktab)
        if not c:
            ap.error("no matching inter cell in the config grid")
        print(render_inter_cell(cfg, c, a.timeblock)); return 0
    ap.error("specify --all or --variant {intra,inter} with its selectors")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
