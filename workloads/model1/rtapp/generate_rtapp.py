#!/usr/bin/env python3
"""
Generate an rt-app JSON config for ONE Model 1 cell.

Model 1 rules baked in via model1lib/config.yaml:
  * exactly ONE thread, policy SCHED_FIFO, m = 1
  * task run  = Q (us)   [Q = round(U * P)]
  * task timer period = P (us), mode absolute
  * implicit deadline = P (FIFO has no explicit deadline; slack is vs. period = P)
  * per-loop logging enabled -> parse/parse_rtapp.py extracts per-job R/C/slack/miss
  * loop = -1 (run forever); the orchestrator stops the cell via the convergence
    stopping rule (N_min..N_max / 3 h guard) by deleting the pod.

Usage:
  generate_rtapp.py --scale tight --u 0.95 --cpu 0 --logdir /results/... \
                    [--config ../config.yaml] [--out rtapp.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import model1lib as m1  # noqa: E402


def build(cfg: dict, scale: str, u: float, cpu: int, logdir: str) -> dict:
    sc = cfg["scales"][scale]
    period_us = sc["period_us"]
    q_us = m1.derive_q_us(u, period_us)
    r = cfg["rtapp"]

    task = {
        "policy": r["policy"],
        "priority": r["priority"],
        "cpus": [cpu],
        "lock_pages": r["lock_pages"],
        "loop": -1,                     # run forever; orchestrator stops the cell
        "run": q_us,                    # busy-compute Q microseconds each period
        "timer": {
            "ref": "rt",
            "period": period_us,        # P
            "mode": "absolute",
        },
    }

    conf = {
        "tasks": {"rt": task},
        "global": {
            "duration": -1,             # unbounded; controlled externally
            "default_policy": r["policy"],
            "lock_pages": r["lock_pages"],
            "calibration": f"CPU{cpu}",  # calibrate the busy loop on the RT core
            "logdir": logdir,
            "log_basename": "rt-app",
            "gnuplot": False,
            "pi_enabled": False,
        },
    }
    return conf


def main() -> int:
    ap = argparse.ArgumentParser(description="Render rt-app JSON for one cell")
    ap.add_argument("--scale", required=True, choices=["tight", "soft"])
    ap.add_argument("--u", required=True, type=float)
    ap.add_argument("--cpu", required=True, type=int,
                    help="logical CPU the RT task is pinned to")
    ap.add_argument("--logdir", required=True,
                    help="in-container dir where rt-app writes its per-loop log")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default="-", help="output path or '-' for stdout")
    args = ap.parse_args()

    cfg = m1.load_config(args.config)
    if args.u not in cfg["scales"][args.scale]["utilizations"]:
        sys.stderr.write(
            f"WARN: U={args.u} not in the {args.scale} grid "
            f"{cfg['scales'][args.scale]['utilizations']}\n"
        )
    conf = build(cfg, args.scale, args.u, args.cpu, args.logdir)
    text = json.dumps(conf, indent=2)
    if args.out == "-":
        print(text)
    else:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        sys.stderr.write(f"wrote {args.out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
