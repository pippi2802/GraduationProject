#!/usr/bin/env python3
"""
plot_all.py — figure set for a Model 1_1 time-block.

Reads results/<tb>/tail-summary.csv (from analyze.py) plus per-cell
jobs.csv / jobs_with_covariates.csv and the calibration curve, and writes PNGs
to results/<tb>/figures/. Linear axes; divergent cells annotated, not clipped
into oblivion (lesson from model1's U=0.94 log-blowout).

Figures:
  fig1_R_ccdf_<scale>.png        response-time CCDF, one curve per U
  fig2_C_vs_R_<scale>.png        compute C vs wall R (median +/- p99 band) vs U
  fig3_R_percentiles_<scale>.png p50/p99/p99.9/max of R vs U
  fig4_cross_scale.png           tight vs soft R-p99 vs U overlay
  fig5_supply_<scale>.png        alpha_eff & Delta_eff vs U with theory lines
  fig6_miss_tardiness.png        deadline-miss rate + max tardiness vs U
  fig7_covariate_scatter.png     per-job (steal+IRQ) vs (R - C) attribution
  fig8_timeseries_<scale>_U<u>.png  R & steal/IRQ over job index for one cell
  fig9_calibration_curve.png     K vs median C (calibration linearity)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402
sys.path.insert(0, str(HERE.parent))
import model1lib as m1  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


def _jobcol(cell_dir: Path, col, cov=False):
    name = "jobs_with_covariates.csv" if cov else "jobs.csv"
    p = cell_dir / name
    out = []
    if not p.exists():
        return out
    with open(p) as fh:
        rdr = csv.reader(fh); header = None
        for r in rdr:
            if not r or r[0].startswith("#"):
                continue
            if header is None:
                header = r; idx = {x: i for i, x in enumerate(header)}; continue
            try:
                out.append(float(r[idx[col]]))
            except (ValueError, KeyError):
                out.append(None)
    return out


def cell_dir_for(tb_dir: Path, scale, u):
    sd = "tight" if scale == "tight" else "soft"
    return tb_dir / sd / f"U{m1.u_label(u)}"


# --------------------------------------------------------------------------- #
def fig1_ccdf(tb_dir, rows_by_scale, figs):
    for scale, rows in rows_by_scale.items():
        fig, ax = plt.subplots()
        cmap = plt.cm.viridis
        for i, r in enumerate(rows):
            u = C.fnum(r["U"])
            cd = cell_dir_for(tb_dir, scale, u)
            R = sorted(v for v in _jobcol(cd, "R_wall_us") if v is not None)
            if not R:
                continue
            n = len(R)
            ccdf = [1 - (k + 1) / n for k in range(n)]
            ax.plot([v / 1000 for v in R], ccdf, color=cmap(i / max(1, len(rows) - 1)),
                    label=f"U={u:g}")
        ax.set_yscale("log")
        ax.set_xlabel("response time R (ms)"); ax.set_ylabel("P(R > x)")
        ax.set_title(f"Response-time CCDF — {C.SCALE_LABEL.get(scale, scale)}")
        ax.legend(fontsize=8, ncol=2)
        C.save(fig, figs, f"fig1_R_ccdf_{scale}.png")


def fig2_c_vs_r(tb_dir, rows_by_scale, figs):
    for scale, rows in rows_by_scale.items():
        U = [C.fnum(r["U"]) for r in rows]
        Cp50 = [C.fnum(r["C_p50"]) for r in rows]
        Rp50 = [C.fnum(r["R_p50"]) for r in rows]
        Rp99 = [C.fnum(r["R_p99"]) for r in rows]
        fig, ax = plt.subplots()
        ax.plot(U, [v / 1000 if v else None for v in Cp50], "o-", color="#2a9d8f", label="C p50 (compute)")
        ax.plot(U, [v / 1000 if v else None for v in Rp50], "s-", color=C.SCALE_COLOR.get(scale), label="R p50 (wall)")
        ax.plot(U, [v / 1000 if v else None for v in Rp99], "^--", color=C.SCALE_COLOR.get(scale), alpha=0.6, label="R p99 (wall)")
        ax.set_xlabel("reserved utilization U = Q/P"); ax.set_ylabel("time (ms)")
        ax.set_title(f"Compute vs wall time — {C.SCALE_LABEL.get(scale, scale)}")
        ax.legend()
        C.save(fig, figs, f"fig2_C_vs_R_{scale}.png")


def fig3_percentiles(tb_dir, rows_by_scale, figs):
    for scale, rows in rows_by_scale.items():
        U = [C.fnum(r["U"]) for r in rows]
        fig, ax = plt.subplots()
        for key, style, lab in (("R_p50", "o-", "p50"), ("R_p99", "s-", "p99"),
                                ("R_p999", "^-", "p99.9"), ("R_max", "d--", "max")):
            y = [(C.fnum(r[key]) or 0) / 1000 for r in rows]
            ax.plot(U, y, style, label=lab)
        ax.set_xlabel("reserved utilization U = Q/P"); ax.set_ylabel("response time R (ms)")
        ax.set_title(f"R percentiles vs U — {C.SCALE_LABEL.get(scale, scale)}")
        ax.legend()
        C.save(fig, figs, f"fig3_R_percentiles_{scale}.png")


def fig4_cross_scale(tb_dir, rows_by_scale, figs):
    fig, ax = plt.subplots()
    for scale, rows in rows_by_scale.items():
        U = [C.fnum(r["U"]) for r in rows]
        y = [(C.fnum(r["R_p99"]) or 0) / 1000 for r in rows]
        ax.plot(U, y, "o-", color=C.SCALE_COLOR.get(scale), label=C.SCALE_LABEL.get(scale, scale))
    ax.set_xlabel("reserved utilization U = Q/P"); ax.set_ylabel("R p99 (ms)")
    ax.set_title("Cross-scale: tail response vs utilization")
    ax.legend()
    C.save(fig, figs, "fig4_cross_scale.png")


def fig5_supply(tb_dir, rows_by_scale, figs):
    for scale, rows in rows_by_scale.items():
        U = [C.fnum(r["U"]) for r in rows]
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
        a1.plot(U, [C.fnum(r["alpha_theory"]) for r in rows], "k--", label="alpha=Q/P (theory)")
        a1.plot(U, [C.fnum(r["alpha_eff"]) for r in rows], "o-", color=C.SCALE_COLOR.get(scale), label="alpha_eff")
        a1.set_xlabel("U"); a1.set_ylabel("bandwidth alpha"); a1.set_title("effective bandwidth"); a1.legend()
        a2.plot(U, [(C.fnum(r["delta_theory_us"]) or 0) / 1000 for r in rows], "k--", label="Delta=2(P-Q) (theory)")
        a2.plot(U, [(C.fnum(r["delta_eff_us"]) or 0) / 1000 for r in rows], "o-", color=C.SCALE_COLOR.get(scale), label="Delta_eff")
        a2.set_xlabel("U"); a2.set_ylabel("service delay Delta (ms)"); a2.set_title("effective delay"); a2.legend()
        fig.suptitle(f"Supply parameters — {C.SCALE_LABEL.get(scale, scale)}")
        C.save(fig, figs, f"fig5_supply_{scale}.png")


def fig6_miss(tb_dir, rows_by_scale, figs):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
    for scale, rows in rows_by_scale.items():
        U = [C.fnum(r["U"]) for r in rows]
        a1.plot(U, [(C.fnum(r["miss_rate"]) or 0) * 100 for r in rows], "o-",
                color=C.SCALE_COLOR.get(scale), label=C.SCALE_LABEL.get(scale, scale))
        a2.plot(U, [(C.fnum(r["tardiness_max"]) or 0) / 1000 for r in rows], "s-",
                color=C.SCALE_COLOR.get(scale), label=C.SCALE_LABEL.get(scale, scale))
    a1.set_xlabel("U"); a1.set_ylabel("deadline-miss rate (%)"); a1.set_title("miss rate"); a1.legend()
    a2.set_xlabel("U"); a2.set_ylabel("max tardiness (ms)"); a2.set_title("max tardiness"); a2.legend()
    C.save(fig, figs, "fig6_miss_tardiness.png")


def fig7_covariate(tb_dir, rows_by_scale, figs):
    fig, ax = plt.subplots()
    for scale, rows in rows_by_scale.items():
        xs, ys = [], []
        for r in rows:
            u = C.fnum(r["U"])
            cd = cell_dir_for(tb_dir, scale, u)
            R = _jobcol(cd, "R_wall_us", cov=True)
            Cc = _jobcol(cd, "C_cputime_us", cov=True)
            steal = _jobcol(cd, "steal_us", cov=True)
            irq = _jobcol(cd, "irq_us", cov=True)
            for i in range(min(len(R), len(Cc), len(steal), len(irq))):
                if None in (R[i], Cc[i], steal[i], irq[i]):
                    continue
                xs.append(steal[i] + irq[i]); ys.append(R[i] - Cc[i])
        if xs:
            ax.scatter(xs, ys, s=4, alpha=0.3, color=C.SCALE_COLOR.get(scale),
                       label=C.SCALE_LABEL.get(scale, scale))
    lim = ax.get_xlim()
    ax.plot(lim, lim, "k:", alpha=0.6, label="R-C = steal+IRQ")
    ax.set_xlabel("I_steal + I_IRQ per job (us)"); ax.set_ylabel("R - C per job (us)")
    ax.set_title("Interference attribution (R-C vs steal+IRQ)")
    ax.legend()
    C.save(fig, figs, "fig7_covariate_scatter.png")


def fig8_timeseries(tb_dir, rows_by_scale, figs):
    for scale, rows in rows_by_scale.items():
        if not rows:
            continue
        r = max(rows, key=lambda x: C.fnum(x["U"]) or 0)  # busiest cell
        u = C.fnum(r["U"])
        cd = cell_dir_for(tb_dir, scale, u)
        R = _jobcol(cd, "R_wall_us", cov=True)
        steal = _jobcol(cd, "steal_us", cov=True)
        irq = _jobcol(cd, "irq_us", cov=True)
        if not R:
            continue
        x = list(range(len(R)))
        fig, ax = plt.subplots()
        ax.plot(x, [v / 1000 if v else None for v in R], color=C.SCALE_COLOR.get(scale), label="R (ms)")
        ax2 = ax.twinx()
        ax2.plot(x, steal, color="#e07a00", alpha=0.5, lw=1, label="steal (us)")
        ax2.plot(x, irq, color="#6a4c93", alpha=0.5, lw=1, label="IRQ (us)")
        ax.set_xlabel("job index"); ax.set_ylabel("R (ms)"); ax2.set_ylabel("interference (us)")
        ax.set_title(f"Time series — {C.SCALE_LABEL.get(scale, scale)} U={u:g}")
        l1, la1 = ax.get_legend_handles_labels(); l2, la2 = ax2.get_legend_handles_labels()
        ax.legend(l1 + l2, la1 + la2, fontsize=8)
        C.save(fig, figs, f"fig8_timeseries_{scale}_U{m1.u_label(u)}.png")


def fig9_calibration(tb_dir, cfg, figs):
    curve = HERE.parent / cfg["calibration"]["curve_file"]
    rows = C.read_csv(curve)
    if not rows:
        print("[plot] no calibration curve; skipping fig9"); return
    K = [C.fnum(r.get("K")) for r in rows]
    Cus = [C.fnum(r.get("median_C_us")) for r in rows]
    fig, ax = plt.subplots()
    ax.plot(K, Cus, "o-", color="#2a9d8f")
    ax.set_xlabel("K (matmul reps / job)"); ax.set_ylabel("median C (us)")
    ax.set_title("Calibration linearity: median compute vs K")
    C.save(fig, figs, "fig9_calibration_curve.png")


def main() -> int:
    ap = argparse.ArgumentParser(description="Model 1_1 figures")
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    C.apply_style()
    cfg = m1.load_config(args.config)
    root = Path(args.results_root) if args.results_root else HERE.parent / cfg["results"]["root"]
    tb_dir = root / args.timeblock
    figs = tb_dir / "figures"
    summary = tb_dir / "tail-summary.csv"
    if not summary.exists():
        print(f"no tail-summary.csv at {summary}; run analyze.py first"); return 1
    rows = C.read_csv(summary)
    rbs = C.by_scale(rows)

    fig1_ccdf(tb_dir, rbs, figs)
    fig2_c_vs_r(tb_dir, rbs, figs)
    fig3_percentiles(tb_dir, rbs, figs)
    fig4_cross_scale(tb_dir, rbs, figs)
    fig5_supply(tb_dir, rbs, figs)
    fig6_miss(tb_dir, rbs, figs)
    fig7_covariate(tb_dir, rbs, figs)
    fig8_timeseries(tb_dir, rbs, figs)
    fig9_calibration(tb_dir, cfg, figs)
    print(f"[plot] figures in {figs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
