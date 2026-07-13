#!/usr/bin/env python3
"""
analyze.py — offline reduction for a Model 3 time-block (CROSS-ARM).

  analyze.py --timeblock LABEL

Model 3 acquires each arm separately (run_model3.py --arm physical, then --arm
sibling), so a time-block dir holds BOTH arms:
  results/<tb>/{physical,sibling}/<scale>/U<u>/{jobs.csv,cell.json,interferer.csv}

For every cell this: (1) joins covariates per per-job CSV (shared
common.rtmetrics.covariates), (2) computes R/C/delay percentiles + deadline-miss +
tardiness (metrics.job_stats), (3) computes supply alpha_eff/Delta_eff
(metrics.reservation_supply). Then it PAIRS the two arms per (scale, U) and emits
the C-INFLATION table — the core Model-3 result:
    inflation = median C(sibling) / median C(physical)
plus the provisioning-vs-delivery proof (alpha_eff / Delta_eff stay intact in the
sibling arm while the miss rate rises).

Outputs (results/<tb>/):
  model3-summary.csv     one row per (arm, scale, U): C/R/delay/miss + supply
  model3-inflation.csv   one row per (scale, U): C_phys, C_sib, inflation, miss delta,
                         alpha_eff/Delta_eff (both arms) — provisioning intact check
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model3lib as m3  # noqa: E402
# shared analysis library (../common/rtmetrics)
sys.path.insert(0, str(HERE.parents[0] / "common"))
from rtmetrics import metrics, covariates  # noqa: E402


def analyze_cell(cell_dir: Path, samples: Path):
    cj = cell_dir / "cell.json"
    if not cj.exists():
        return None
    meta = json.loads(cj.read_text())
    covariates.join_percell(cell_dir, samples)
    P, Q = meta["P_us"], meta["Q_us"]
    st = metrics.job_stats(cell_dir / "jobs.csv") or {}
    sup = metrics.reservation_supply(cell_dir / "jobs.csv", Q, P)
    meta["derived"] = {"tail": st, "supply": sup}
    cj.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta, st, sup


def main() -> int:
    ap = argparse.ArgumentParser(description="Model 3 offline analysis (cross-arm)")
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = m3.load_config(args.config)
    root = Path(args.results_root) if args.results_root else HERE / cfg["results"]["root"]
    tb = root / args.timeblock
    samples = tb / "samples"
    if not tb.exists():
        print(f"no results at {tb}"); return 1

    # per-cell reduction -> summary rows keyed by (scale, U) per arm
    rows = []
    by_key = {}   # (scale, u) -> {arm: (st, sup, meta)}
    for cj in sorted(tb.glob("*/*/U*/cell.json")):
        cell_dir = cj.parent
        out = analyze_cell(cell_dir, samples)
        if out is None:
            continue
        meta, st, sup = out
        arm = meta["arm"]; scale = meta["scale"]; u = meta["U"]
        rows.append({
            "arm": arm, "scale": scale, "U": u, "P_us": meta["P_us"], "Q_us": meta["Q_us"],
            "K": meta["K"], "sibling_load": meta.get("sibling_load"),
            "c_baseline_us": meta.get("c_baseline_us"),
            "n": st.get("n"), "miss_rate": st.get("miss_rate"),
            "C_p50": st.get("C_p50"), "C_p99": st.get("C_p99"), "C_max": st.get("C_max"),
            "R_p50": st.get("R_p50"), "R_p99": st.get("R_p99"),
            "R_p999": st.get("R_p999"), "R_max": st.get("R_max"),
            "delay_p50": st.get("delay_p50"), "delay_p99": st.get("delay_p99"),
            "dispatch_max": st.get("dispatch_max"), "tardiness_max": st.get("tardiness_max"),
            "alpha_theory": sup.get("alpha_theory"), "alpha_eff": sup.get("alpha_eff"),
            "delta_theory_us": sup.get("delta_theory_us"), "delta_eff_us": sup.get("delta_eff_us"),
            "alpha_violation": 1 if sup.get("alpha_violation") else 0,
            "rt_cpu": meta.get("cpu_used"),
            "sibling_cpu": (meta.get("interferer") or {}).get("sibling_cpu"),
            "stop_reason": meta.get("stop_reason"),
        })
        by_key.setdefault((scale, u), {})[arm] = (st, sup, meta)

    if rows:
        cols = list(rows[0].keys())
        out = tb / "model3-summary.csv"
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in sorted(rows, key=lambda x: (x["arm"], x["scale"], x["U"])):
                w.writerow(r)
        print(f"[analyze] wrote {out} ({len(rows)} rows)")
    else:
        print("[analyze] no cells with data"); return 0

    # cross-arm C-inflation table (needs both arms for a (scale,U))
    infl = []
    for (scale, u), arms in sorted(by_key.items()):
        if "physical" not in arms or "sibling" not in arms:
            continue
        (pst, psup, pmeta) = arms["physical"]
        (sst, ssup, smeta) = arms["sibling"]
        c_phys = pst.get("C_p50"); c_sib = sst.get("C_p50")
        inflation = (c_sib / c_phys) if (c_phys and c_sib and c_phys > 0) else None
        infl.append({
            "scale": scale, "U": u, "P_us": pmeta["P_us"], "Q_us": pmeta["Q_us"],
            "K": pmeta["K"], "c_baseline_us": pmeta.get("c_baseline_us"),
            "sibling_load": smeta.get("sibling_load"),
            "C_p50_physical": c_phys, "C_p50_sibling": c_sib,
            "C_inflation_factor": round(inflation, 4) if inflation else None,
            "C_over_Q_physical": round(c_phys / pmeta["Q_us"], 4) if c_phys else None,
            "C_over_Q_sibling": round(c_sib / pmeta["Q_us"], 4) if c_sib else None,
            "miss_rate_physical": pst.get("miss_rate"), "miss_rate_sibling": sst.get("miss_rate"),
            "R_p99_physical": pst.get("R_p99"), "R_p99_sibling": sst.get("R_p99"),
            # provisioning-vs-delivery proof: server still delivered Q in the sibling arm
            "alpha_eff_physical": psup.get("alpha_eff"), "alpha_eff_sibling": ssup.get("alpha_eff"),
            "delta_eff_us_physical": psup.get("delta_eff_us"), "delta_eff_us_sibling": ssup.get("delta_eff_us"),
            "alpha_theory": psup.get("alpha_theory"),
        })
    if infl:
        cols = list(infl[0].keys())
        out = tb / "model3-inflation.csv"
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in sorted(infl, key=lambda x: (x["scale"], x["U"])):
                w.writerow(r)
        print(f"[analyze] wrote {out} ({len(infl)} paired cells)")
    else:
        print("[analyze] no (scale,U) had BOTH arms; run both --arm physical and --arm sibling "
              "into the same --timeblock to get the C-inflation table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
