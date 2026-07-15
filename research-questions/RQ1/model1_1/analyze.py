#!/usr/bin/env python3
"""
analyze.py — offline reduction for a Model 1_1 time-block.

For every cell (results/<tb>/<scale>/U<u>/jobs.csv):
  1. run join_covariates.py  -> jobs_with_covariates.csv
  2. compute supply (alpha_eff, Delta_eff) from the server stream
  3. compute R/C/delay percentiles + deadline-miss rate + tardiness
Writes results/<tb>/tail-summary.csv (one row per cell) and folds supply +
tail stats back into each cell.json ("derived").
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model1lib as m1  # noqa: E402
sys.path.insert(0, str(HERE / "parse"))
import supply as supplymod  # noqa: E402
sys.path.insert(0, str(HERE.parent / "common"))
from rtmetrics import metrics, covariates  # noqa: E402


def cell_stats(cell_dir: Path):
    """Per-cell R/C/delay percentiles (shared common/rtmetrics.metrics.job_stats)."""
    return metrics.job_stats(cell_dir / "jobs.csv")


def main() -> int:
    ap = argparse.ArgumentParser(description="Model 1_1 offline analysis")
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = m1.load_config(args.config)
    root = Path(args.results_root) if args.results_root else HERE / cfg["results"]["root"]
    tb = root / args.timeblock
    samples = tb / "samples"
    if not tb.exists():
        print(f"no results at {tb}"); return 1

    rows = []
    for cellj in sorted(tb.glob("*/U*/cell.json")):
        cd = cellj.parent
        meta = json.loads(cellj.read_text())
        # 1. covariate join (in-process; sampler streams are parsed once and cached
        #    across all cells, so a large samples/ dir is not re-read per cell)
        covariates.join_model1_1(cd, samples)
        # 2. supply
        try:
            sup = supplymod.compute(cd, samples)
        except Exception as e:  # noqa: BLE001
            sup = {"error": str(e)}
        # 3. tail stats
        st = cell_stats(cd) or {}
        meta["derived"] = {"supply": sup, "tail": st}
        cellj.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        rows.append({
            "scale": meta["scale"], "U": meta["U"], "P_us": meta["P_us"], "Q_us": meta["Q_us"],
            "K": meta.get("K"), "n": st.get("n"), "miss_rate": st.get("miss_rate"),
            "R_p50": st.get("R_p50"), "R_p99": st.get("R_p99"),
            "R_p999": st.get("R_p999"), "R_max": st.get("R_max"),
            "C_p50": st.get("C_p50"), "C_p99": st.get("C_p99"),
            "dispatch_max": st.get("dispatch_max"), "midpreempt_max": st.get("midpreempt_max"),
            "tardiness_max": st.get("tardiness_max"),
            "alpha_theory": sup.get("alpha_theory"), "alpha_eff": sup.get("alpha_eff"),
            "delta_theory_us": sup.get("delta_theory_us"), "delta_eff_us": sup.get("delta_eff_us"),
            "stop_reason": meta.get("stop_reason"),
        })

    if rows:
        cols = list(rows[0].keys())
        out = tb / "tail-summary.csv"
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in sorted(rows, key=lambda x: (x["scale"], x["U"])):
                w.writerow(r)
        print(f"[analyze] wrote {out} ({len(rows)} cells)")
    else:
        print("[analyze] no cells with data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
