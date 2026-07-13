#!/usr/bin/env python3
"""
analyze.py — offline reduction for a Model 2 time-block.

  analyze.py --variant {intra,inter} --timeblock LABEL

For every cell it: (1) joins covariates per per-job CSV, (2) computes supply
(alpha_eff, Delta_eff) per reservation, (3) computes R/C/delay percentiles +
deadline-miss + tardiness. Writes a per-variant summary CSV and folds the derived
stats back into each cell.json.

  intra: one row PER TASK (victim flagged) -> intra-summary.csv. The signature of
         inner contention is per-task R spread + Delta_eff GROWING with k while the
         SERVER still keeps its full Q (container alpha ~= U).
  inter: one row PER CELL (the measured target) -> inter-summary.csv. The signature
         of an isolation leak is target alpha_eff SLOPING DOWN as neighbour load
         rises (flat = firewall holds).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model2lib as m2  # noqa: E402
sys.path.insert(0, str(HERE.parent / "common"))
from rtmetrics import metrics, covariates  # noqa: E402

job_stats = metrics.job_stats


def join_cell(cell_dir: Path, samples: Path):
    covariates.join_percell(cell_dir, samples)


# --------------------------------------------------------------------------- #
def analyze_intra(tb: Path, samples: Path):
    rows = []
    for cellj in sorted(tb.glob("intra/*/*/cell.json")):
        cd = cellj.parent
        meta = json.loads(cellj.read_text())
        join_cell(cd, samples)
        P, Q = meta["P_us"], meta["Q_us"]
        task_files = [t["file"] for t in meta["placements"]["tasks"]]
        # container-level supply: all tasks share ONE reservation Q
        csup = metrics.reservation_supply([cd / f for f in task_files], Q, P)
        derived_tasks = []
        for t in meta["placements"]["tasks"]:
            st = job_stats(cd / t["file"]) or {}
            # per-task supply vs the task's OWN share (target_C ~= task Q)
            tsup = metrics.reservation_supply(cd / t["file"], t["target_C_us"], P)
            derived_tasks.append({"file": t["file"], "role": t["role"], "tail": st, "supply": tsup})
            rows.append({
                "scale": meta["scale"], "U": meta["U"], "P_us": P, "Q_us": Q,
                "k": meta["k"], "split": meta["split"],
                "task_index": t["index"], "task_u": t["u"], "role": t["role"] or "equal",
                "is_victim": 1 if t["role"] == "victim" else 0,
                "K": t["K"], "n": st.get("n"), "miss_rate": st.get("miss_rate"),
                "R_p50": st.get("R_p50"), "R_p99": st.get("R_p99"),
                "R_p999": st.get("R_p999"), "R_max": st.get("R_max"),
                "C_p50": st.get("C_p50"), "delay_p99": st.get("delay_p99"),
                "dispatch_max": st.get("dispatch_max"), "tardiness_max": st.get("tardiness_max"),
                "container_alpha_theory": csup.get("alpha_theory"),
                "container_alpha_eff": csup.get("alpha_eff"),
                "delta_theory_us": csup.get("delta_theory_us"),
                "delta_eff_us": csup.get("delta_eff_us"),
                "stop_reason": meta.get("stop_reason"),
            })
        meta["derived"] = {"container_supply": csup, "tasks": derived_tasks}
        cellj.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return rows, ("intra-summary.csv")


def analyze_inter(tb: Path, samples: Path):
    rows = []
    for cellj in sorted(tb.glob("inter/*/*/*/cell.json")):
        cd = cellj.parent
        meta = json.loads(cellj.read_text())
        join_cell(cd, samples)
        P, Q = meta["P_us"], meta["target_Q_us"]
        st = job_stats(cd / "target.csv") or {}
        sup = metrics.reservation_supply(cd / "target.csv", Q, P)
        meta["derived"] = {"target_tail": st, "target_supply": sup}
        cellj.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        adm = meta.get("admission", {})
        rows.append({
            "scale": meta["scale"], "arm": meta["arm"], "cell_id": meta["cell_id"],
            "target_U": meta["target_U"], "P_us": P, "target_Q_us": Q,
            "n_neighbours": meta["n_neighbours"],
            "aggregate_neighbour_u": meta["aggregate_neighbour_u"],
            "oversubscribe": 1 if meta["oversubscribe"] else 0,
            "neighbours_admitted": adm.get("neighbours_admitted"),
            "colocated_with_target": adm.get("colocated_with_target"),
            "n": st.get("n"), "miss_rate": st.get("miss_rate"),
            "R_p50": st.get("R_p50"), "R_p99": st.get("R_p99"),
            "R_p999": st.get("R_p999"), "R_max": st.get("R_max"),
            "C_p50": st.get("C_p50"), "delay_p99": st.get("delay_p99"),
            "dispatch_max": st.get("dispatch_max"), "tardiness_max": st.get("tardiness_max"),
            "alpha_theory": sup.get("alpha_theory"), "alpha_eff": sup.get("alpha_eff"),
            "delta_theory_us": sup.get("delta_theory_us"), "delta_eff_us": sup.get("delta_eff_us"),
            "alpha_violation": 1 if sup.get("alpha_violation") else 0,
            "stop_reason": meta.get("stop_reason"),
        })
    return rows, ("inter-summary.csv")


def main() -> int:
    ap = argparse.ArgumentParser(description="Model 2 offline analysis")
    ap.add_argument("--variant", required=True, choices=["intra", "inter"])
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = m2.load_config(args.config)
    root = Path(args.results_root) if args.results_root else HERE / cfg["results"]["root"]
    tb = root / args.timeblock
    samples = tb / "samples"
    if not tb.exists():
        print(f"no results at {tb}"); return 1

    if args.variant == "intra":
        rows, outname = analyze_intra(tb, samples)
        sortkey = lambda x: (x["scale"], x["U"], x["k"], x["split"], x["task_index"])
    else:
        rows, outname = analyze_inter(tb, samples)
        sortkey = lambda x: (x["scale"], x["arm"], x["target_U"], x["aggregate_neighbour_u"])

    if rows:
        cols = list(rows[0].keys())
        out = tb / outname
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in sorted(rows, key=sortkey):
                w.writerow(r)
        print(f"[analyze] wrote {out} ({len(rows)} rows)")
    else:
        print("[analyze] no cells with data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
