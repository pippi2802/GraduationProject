#!/usr/bin/env python3
"""
Emit shell `export`s for one cell (or the canary), derived entirely from
config.yaml via model1lib. Keeps the manifest renderer DRY — nothing about
Q/P/m/units/images/paths is duplicated in bash.

Usage:
  cell_env.py <scale> <U> <timeblock>            # RT cell
  cell_env.py --canary <timeblock>               # canary cell
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import model1lib as m1  # noqa: E402


def emit(cell: dict, cfg: dict, timeblock: str, cpu_key: str):
    res = cfg["kubedeadline_reservation_spec"]
    img = cfg["image"]
    host_root = cfg["results"]["host_path"]
    host_path = f"{host_root}/{timeblock}/{cell['scale_dir']}/U{m1.u_label(cell['u'])}"
    name = cell["cell_name"]
    exports = {
        "CELL_ID": name,
        "NAMESPACE": "model1",
        "RES_RUNTIME": cell["reservation_runtime"],
        "RES_PERIOD": cell["reservation_period"],
        "RES_COUNT": cell["reservation_count"],
        "RES_CLASS": res["dra"]["resource_class_name"] if "dra" in res else "rt.example.com",
        "SCALE": cell["scale"],
        "SCALE_DIR": cell["scale_dir"],
        "U_LABEL": m1.u_label(cell["u"]),
        "PERIOD_US": cell["period_us"],
        "Q_US": cell["q_us"],
        "BASE_IMAGE": img["base_image"],
        "RTAPP_PKG": img["rtapp_apt_package"],
        "PULL_POLICY": img["pull_policy"],
        "HOST_RESULTS_PATH": host_path,
        "CPU_KEY": cpu_key,
        "CM_NAME": name + "-rtapp",
    }
    for k, v in exports.items():
        print(f'export {k}="{v}"')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canary", action="store_true")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    cfg = m1.load_config(a.config)

    if a.canary:
        timeblock = a.args[0] if a.args else "tb-example"
        cell = m1.canary_cell(cfg)
        emit(cell, cfg, timeblock, cpu_key="canary_cpu")
        return 0

    if len(a.args) < 3:
        sys.stderr.write("usage: cell_env.py <scale> <U> <timeblock>\n")
        return 2
    scale, u, timeblock = a.args[0], float(a.args[1]), a.args[2]
    sc = cfg["scales"][scale]
    q_us = m1.derive_q_us(u, sc["period_us"])
    runtime, period = m1.reservation_qp(cfg, q_us, sc["period_us"])
    cell = {
        "cell_id": m1.cell_id(scale, u),
        "cell_name": m1.k8s_name(scale, u),
        "scale": scale, "scale_dir": sc["dir"],
        "period_us": sc["period_us"], "u": u, "q_us": q_us,
        "reservation_runtime": runtime, "reservation_period": period,
        # 'count' = number of cores m; driver auto-selects the CPU.
        "reservation_count": cfg["cores_per_container"],
    }
    emit(cell, cfg, timeblock, cpu_key="rt_cpu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
