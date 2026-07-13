#!/usr/bin/env python3
"""
analyze.py — offline reduction for a Model 4 time-block (CROSS-ARM).

  analyze.py --timeblock LABEL

Model 4 acquires each arm separately (run_model4.py --arm off, then --arm on), so a
time-block dir holds BOTH arms:
  results/<tb>/{off,on}/<scale>/U<u>/{jobs.csv,cell.json}

For every cell this: (1) joins covariates per per-job CSV (shared
common.rtmetrics.covariates -> per-job irq_us / softirq_us / steal_us inside the job
window), (2) computes R/C/delay percentiles + deadline-miss + tardiness
(metrics.job_stats), (3) computes supply alpha_eff/Delta_eff
(metrics.reservation_supply). Then it PAIRS the two arms per (scale, U) and emits the
R-TAIL inflation table — the core Model-4 result — plus the IRQ attribution.

Outputs (results/<tb>/):
  model4-summary.csv     one row per (arm, scale, U): R-tail/C/delay/miss + supply + IRQ
  model4-tail.csv        one row per (scale, U): off vs on R-p99/p99.9/max, miss delta,
                         Delta_eff (replenishment jitter), mean per-job I_IRQ
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model4lib as m4  # noqa: E402
sys.path.insert(0, str(HERE.parents[0] / "common"))
from rtmetrics import metrics, covariates  # noqa: E402


def _mean_col(csv_path: Path, col: str):
    """Mean of one numeric column of a *_with_covariates.csv (e.g. per-job irq_us)."""
    p = Path(csv_path)
    if not p.exists():
        return None
    vals = []
    with open(p) as fh:
        header = None
        for r in csv.reader(fh):
            if not r or r[0].startswith("#"):
                continue
            if header is None:
                header = r; idx = {x: i for i, x in enumerate(header)}; continue
            try:
                vals.append(float(r[idx[col]]))
            except (ValueError, KeyError):
                continue
    return sum(vals) / len(vals) if vals else None


def analyze_cell(cell_dir: Path, samples: Path):
    cj = cell_dir / "cell.json"
    if not cj.exists():
        return None
    meta = json.loads(cj.read_text())
    covariates.join_percell(cell_dir, samples)
    P, Q = meta["P_us"], meta["Q_us"]
    st = metrics.job_stats(cell_dir / "jobs.csv") or {}
    sup = metrics.reservation_supply(cell_dir / "jobs.csv", Q, P)
    cov = cell_dir / "jobs_with_covariates.csv"
    irq_mean = _mean_col(cov, "irq_us")
    softirq_mean = _mean_col(cov, "softirq_us")
    steal_mean = _mean_col(cov, "steal_us")
    meta["derived"] = {"tail": st, "supply": sup, "irq_us_mean": irq_mean,
                       "softirq_us_mean": softirq_mean, "steal_us_mean": steal_mean}
    cj.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta, st, sup, {"irq_us_mean": irq_mean, "softirq_us_mean": softirq_mean,
                           "steal_us_mean": steal_mean}


def main() -> int:
    ap = argparse.ArgumentParser(description="Model 4 offline analysis (cross-arm)")
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = m4.load_config(args.config)
    root = Path(args.results_root) if args.results_root else HERE / cfg["results"]["root"]
    tb = root / args.timeblock
    samples = tb / "samples"
    if not tb.exists():
        print(f"no results at {tb}"); return 1

    rows = []
    by_key = {}   # (scale, u) -> {arm: (st, sup, cov, meta)}
    for cj in sorted(tb.glob("*/*/U*/cell.json")):
        cell_dir = cj.parent
        out = analyze_cell(cell_dir, samples)
        if out is None:
            continue
        meta, st, sup, cov = out
        arm = meta["arm"]; scale = meta["scale"]; u = meta["U"]
        steered = (meta.get("irq_map") or {}).get("steered_count")
        rows.append({
            "arm": arm, "scale": scale, "U": u, "P_us": meta["P_us"], "Q_us": meta["Q_us"],
            "K": meta["K"], "steered_irq_lines": steered,
            "irq_rate_delta_per_s": (meta.get("irq_preflight") or {}).get("irq_rate_delta_per_s"),
            "n": st.get("n"), "miss_rate": st.get("miss_rate"),
            "C_p50": st.get("C_p50"), "C_p99": st.get("C_p99"),
            "R_p50": st.get("R_p50"), "R_p99": st.get("R_p99"),
            "R_p999": st.get("R_p999"), "R_max": st.get("R_max"),
            "delay_p50": st.get("delay_p50"), "delay_p99": st.get("delay_p99"),
            "dispatch_max": st.get("dispatch_max"), "tardiness_max": st.get("tardiness_max"),
            "irq_us_mean": cov.get("irq_us_mean"), "softirq_us_mean": cov.get("softirq_us_mean"),
            "steal_us_mean": cov.get("steal_us_mean"),
            "alpha_theory": sup.get("alpha_theory"), "alpha_eff": sup.get("alpha_eff"),
            "delta_theory_us": sup.get("delta_theory_us"), "delta_eff_us": sup.get("delta_eff_us"),
            "rt_cpu": meta.get("cpu_used"), "stop_reason": meta.get("stop_reason"),
        })
        by_key.setdefault((scale, u), {})[arm] = (st, sup, cov, meta)

    if rows:
        cols = list(rows[0].keys())
        out = tb / "model4-summary.csv"
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in sorted(rows, key=lambda x: (x["arm"], x["scale"], x["U"])):
                w.writerow(r)
        print(f"[analyze] wrote {out} ({len(rows)} rows)")
    else:
        print("[analyze] no cells with data"); return 0

    # cross-arm R-tail inflation table (needs both arms for a (scale,U))
    tail = []
    for (scale, u), arms in sorted(by_key.items()):
        if "off" not in arms or "on" not in arms:
            continue
        (ost, osup, ocov, ometa) = arms["off"]
        (nst, nsup, ncov, nmeta) = arms["on"]
        def infl(a, b):
            return round(b / a, 4) if (a and b and a > 0) else None
        tail.append({
            "scale": scale, "U": u, "P_us": ometa["P_us"], "Q_us": ometa["Q_us"], "K": ometa["K"],
            "R_p99_off": ost.get("R_p99"), "R_p99_on": nst.get("R_p99"),
            "R_p99_inflation": infl(ost.get("R_p99"), nst.get("R_p99")),
            "R_p999_off": ost.get("R_p999"), "R_p999_on": nst.get("R_p999"),
            "R_p999_inflation": infl(ost.get("R_p999"), nst.get("R_p999")),
            "R_max_off": ost.get("R_max"), "R_max_on": nst.get("R_max"),
            "miss_rate_off": ost.get("miss_rate"), "miss_rate_on": nst.get("miss_rate"),
            # replenishment jitter: worst dispatch delay grows under on-core IRQs
            "delta_eff_us_off": osup.get("delta_eff_us"), "delta_eff_us_on": nsup.get("delta_eff_us"),
            "alpha_eff_off": osup.get("alpha_eff"), "alpha_eff_on": nsup.get("alpha_eff"),
            # positive attribution: per-job IRQ CPU-time (on) vs steal (should be flat)
            "irq_us_mean_off": ocov.get("irq_us_mean"), "irq_us_mean_on": ncov.get("irq_us_mean"),
            "steal_us_mean_on": ncov.get("steal_us_mean"),
            "steered_irq_lines_on": (nmeta.get("irq_map") or {}).get("steered_count"),
        })
    if tail:
        cols = list(tail[0].keys())
        out = tb / "model4-tail.csv"
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in sorted(tail, key=lambda x: (x["scale"], x["U"])):
                w.writerow(r)
        print(f"[analyze] wrote {out} ({len(tail)} paired cells)")
    else:
        print("[analyze] no (scale,U) had BOTH arms; run both --arm off and --arm on "
              "into the same --timeblock to get the tail-inflation table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
