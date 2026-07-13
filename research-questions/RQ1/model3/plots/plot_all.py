#!/usr/bin/env python3
"""
plot_all.py — figure set for a Model 3 time-block (hyper-thread vs physical core).

  plot_all.py --timeblock LABEL
  plot_all.py --timeblock LABEL --dose-timeblocks tb-lightRUN tb-medRUN tb-satRUN

Reads the summaries from analyze.py (model3-summary.csv, model3-inflation.csv) plus
per-cell per-job CSVs, and writes PNG+PDF to results/<tb>/figures/. Reuses the
SHARED plotting helpers in ../../common/rtmetrics/plotting.py. Linear axes;
divergent cells annotated, not clipped.

Figures:
  1. C distribution physical vs sibling, per (scale, U)         [the core C-inflation figure]
  2. C-inflation factor vs U, tight & soft OVERLAID             [execution-layer fingerprint]
  3. R percentiles + deadline-miss rate vs U, physical vs sibling, per scale
  4. Provisioning-vs-delivery: alpha_eff & Delta_eff vs U (intact in sibling) + miss rate
  5. Dose-response: C-inflation vs sibling-load at fixed U      [needs --dose-timeblocks]
  6. Covariate correlation: R-C vs steal+IRQ per job (per scale)
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import model3lib as m3  # noqa: E402
# shared plotting helpers (../../common/rtmetrics)
sys.path.insert(0, str(HERE.parents[1] / "common"))
from rtmetrics import plotting as P  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ARM_COLOR = {"physical": "#1d4e89", "sibling": "#c1121f"}
ARM_LABEL = {"physical": "physical (clean core)", "sibling": "sibling (HT interferer)"}


def _sd(cfg, scale):
    return cfg["scales"][scale]["dir"]


def cell_dir(tb_dir, cfg, arm, scale, u):
    arm_dir = cfg["arms"][arm]["dir"]
    return tb_dir / arm_dir / _sd(cfg, scale) / f"U{m3.u_label(u)}"


# ============================ FIG 1 ======================================== #
def fig_c_distribution(tb_dir, cfg, rows, figs):
    """C histogram/CCDF physical vs sibling, one panel per (scale, U)."""
    combos = sorted({(r["scale"], P.fnum(r["U"])) for r in rows})
    for scale, u in combos:
        fig, ax = plt.subplots()
        drew = False
        for arm in ("physical", "sibling"):
            cd = cell_dir(tb_dir, cfg, arm, scale, u)
            Cvals = [v for v in P.jobcol(cd, "jobs.csv", "C_cputime_us") if v is not None]
            if not Cvals:
                continue
            P.ccdf(ax, Cvals, color=ARM_COLOR[arm], label=ARM_LABEL[arm])
            drew = True
        if not drew:
            plt.close(fig); continue
        # Q line (deadline budget); C above Q => miss even if server delivered Q
        Q = next((P.fnum(r["Q_us"]) for r in rows
                  if r["scale"] == scale and P.fnum(r["U"]) == u), None)
        if Q:
            ax.axvline(Q / 1000, color="k", ls="--", alpha=0.7, label="Q = round(U·P)")
        ax.set_yscale("log")
        ax.set_xlabel("execution time C (ms)"); ax.set_ylabel("P(C > x)")
        ax.set_title(f"C distribution: physical vs sibling — "
                     f"{P.SCALE_LABEL.get(scale, scale)} U={u:g}")
        ax.legend(fontsize=9)
        P.save(fig, figs, f"fig_c_ccdf_{scale}_U{m3.u_label(u)}")


# ============================ FIG 2 ======================================== #
def fig_inflation_vs_u(tb_dir, cfg, infl, figs):
    """C-inflation factor vs U, tight & soft OVERLAID (period-independent => flat)."""
    if not infl:
        return
    fig, ax = plt.subplots()
    for scale in sorted({r["scale"] for r in infl}):
        rs = sorted((r for r in infl if r["scale"] == scale), key=lambda x: P.fnum(x["U"]))
        u = [P.fnum(r["U"]) for r in rs]
        f = [P.fnum(r["C_inflation_factor"]) for r in rs]
        ax.plot(u, f, "o-", color=P.SCALE_COLOR.get(scale), label=P.SCALE_LABEL.get(scale, scale))
    ax.axhline(1.0, color="k", ls=":", alpha=0.6, label="no inflation")
    # ~2.0 aggregate-util line is per-node, not per-U; annotate the physical-capacity idea
    ax.set_xlabel("utilisation U (per cell)")
    ax.set_ylabel("C-inflation = median C(sibling) / C(physical)")
    ax.set_title("Hyper-thread C-inflation vs U\n"
                 "similar relative inflation at both scales => execution-layer break")
    ax.legend(fontsize=9)
    P.save(fig, figs, "fig_c_inflation_vs_u")


# ============================ FIG 3 ======================================== #
def fig_r_and_miss(tb_dir, cfg, rows, figs):
    """R percentiles + deadline-miss rate vs U, physical vs sibling, per scale."""
    for scale in sorted({r["scale"] for r in rows}):
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
        for arm in ("physical", "sibling"):
            rs = sorted((r for r in rows if r["scale"] == scale and r["arm"] == arm),
                        key=lambda x: P.fnum(x["U"]))
            if not rs:
                continue
            u = [P.fnum(r["U"]) for r in rs]
            a1.plot(u, [(P.fnum(r["R_p99"]) or 0) / 1000 for r in rs], "o-",
                    color=ARM_COLOR[arm], label=f"{ARM_LABEL[arm]} p99")
            a1.plot(u, [(P.fnum(r["R_p50"]) or 0) / 1000 for r in rs], "s--",
                    color=ARM_COLOR[arm], alpha=0.5, label=f"{ARM_LABEL[arm]} p50")
            a2.plot(u, [P.fnum(r["miss_rate"]) for r in rs], "o-",
                    color=ARM_COLOR[arm], label=ARM_LABEL[arm])
        a1.set_xlabel("U"); a1.set_ylabel("response time R (ms)")
        a1.set_title("R percentiles"); a1.legend(fontsize=8)
        a2.set_xlabel("U"); a2.set_ylabel("deadline-miss rate")
        a2.set_title("miss rate"); a2.legend(fontsize=8)
        fig.suptitle(f"Model 3 R & miss vs U — {P.SCALE_LABEL.get(scale, scale)}")
        P.save(fig, figs, f"fig_R_miss_vs_u_{scale}")


# ============================ FIG 4 ======================================== #
def fig_provisioning(tb_dir, cfg, infl, figs):
    """alpha_eff & Delta_eff stay ~intact in the sibling arm while miss rate rises:
    'the server got Q but the task still missed' (a provisioning failure)."""
    if not infl:
        return
    for scale in sorted({r["scale"] for r in infl}):
        rs = sorted((r for r in infl if r["scale"] == scale), key=lambda x: P.fnum(x["U"]))
        u = [P.fnum(r["U"]) for r in rs]
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
        a1.plot(u, [P.fnum(r["alpha_eff_physical"]) for r in rs], "o-",
                color=ARM_COLOR["physical"], label="alpha_eff physical")
        a1.plot(u, [P.fnum(r["alpha_eff_sibling"]) for r in rs], "s-",
                color=ARM_COLOR["sibling"], label="alpha_eff sibling")
        a1.plot(u, [P.fnum(r["alpha_theory"]) for r in rs], "k--", label="alpha = Q/P (theory)")
        a1.set_xlabel("U"); a1.set_ylabel("effective bandwidth alpha_eff")
        a1.set_title("server delivered Q in BOTH arms"); a1.legend(fontsize=8)
        a2.plot(u, [P.fnum(r["miss_rate_sibling"]) for r in rs], "o-",
                color=ARM_COLOR["sibling"], label="miss rate (sibling)")
        a2b = a2.twinx()
        a2b.plot(u, [P.fnum(r["C_inflation_factor"]) for r in rs], "^--",
                 color="#555", label="C-inflation")
        a2.set_xlabel("U"); a2.set_ylabel("sibling miss rate")
        a2b.set_ylabel("C-inflation factor")
        a2.set_title("...yet the task missed (C-inflation)")
        a2.legend(fontsize=8, loc="upper left"); a2b.legend(fontsize=8, loc="lower right")
        fig.suptitle(f"Provisioning vs delivery — {P.SCALE_LABEL.get(scale, scale)}")
        P.save(fig, figs, f"fig_provisioning_vs_delivery_{scale}")


# ============================ FIG 5 ======================================== #
def fig_dose_response(cfg, root, dose_tbs, figs):
    """C-inflation vs sibling-load at the fixed dose_response_utilization.

    Each entry in dose_tbs is a sibling-arm run at a different --sibling-load whose
    model3-inflation.csv records the load; we read the fixed-U row from each and
    order by duty. If none provided, skip.
    """
    if not dose_tbs:
        return
    u_target = cfg["interferer"]["dose_response_utilization"]
    duty = {lv: d["duty"] for lv, d in cfg["interferer"]["sibling_load_levels"].items()}
    per_scale = defaultdict(list)   # scale -> [(duty, level, inflation)]
    for tbname in dose_tbs:
        infl_csv = root / tbname / "model3-inflation.csv"
        if not infl_csv.exists():
            print(f"[plot] dose: missing {infl_csv}; skip"); continue
        for r in P.read_csv(infl_csv):
            if abs(P.fnum(r["U"]) - u_target) > 1e-9:
                continue
            lv = r.get("sibling_load")
            per_scale[r["scale"]].append((duty.get(lv, 0.0), lv, P.fnum(r["C_inflation_factor"])))
    if not per_scale:
        return
    fig, ax = plt.subplots()
    for scale, pts in sorted(per_scale.items()):
        pts.sort(key=lambda x: x[0])
        ax.plot([p[0] for p in pts], [p[2] for p in pts], "o-",
                color=P.SCALE_COLOR.get(scale), label=P.SCALE_LABEL.get(scale, scale))
        for d, lv, f in pts:
            if f is not None:
                ax.annotate(lv, (d, f), fontsize=7, textcoords="offset points", xytext=(4, 4))
    ax.axhline(1.0, color="k", ls=":", alpha=0.6, label="no inflation")
    ax.set_xlabel("interferer duty (sibling-load)")
    ax.set_ylabel("C-inflation factor")
    ax.set_title(f"Dose-response: C-inflation vs sibling load @ U={u_target:g}")
    ax.legend(fontsize=9)
    P.save(fig, figs, "fig_dose_response")


# ============================ FIG 6 ======================================== #
def fig_covariate(tb_dir, cfg, rows, figs):
    """R-C vs steal+IRQ per job (delay-layer covariate attribution), per scale."""
    fig, ax = plt.subplots()
    any_pts = False
    for scale in sorted({r["scale"] for r in rows}):
        for arm in ("physical", "sibling"):
            xs, ys = [], []
            for r in (x for x in rows if x["scale"] == scale and x["arm"] == arm):
                cd = cell_dir(tb_dir, cfg, arm, scale, P.fnum(r["U"]))
                Rc = P.jobcol(cd, "jobs.csv", "R_wall_us", cov=True)
                Cc = P.jobcol(cd, "jobs.csv", "C_cputime_us", cov=True)
                steal = P.jobcol(cd, "jobs.csv", "steal_us", cov=True)
                irq = P.jobcol(cd, "jobs.csv", "irq_us", cov=True)
                for i in range(min(len(Rc), len(Cc), len(steal), len(irq))):
                    if None in (Rc[i], Cc[i], steal[i], irq[i]):
                        continue
                    xs.append(steal[i] + irq[i]); ys.append(Rc[i] - Cc[i])
            if xs:
                any_pts = True
                ax.scatter(xs, ys, s=4, alpha=0.3, color=ARM_COLOR[arm],
                           label=f"{ARM_LABEL[arm]} ({scale})")
    if not any_pts:
        plt.close(fig); return
    lim = ax.get_xlim()
    ax.plot(lim, lim, "k:", alpha=0.6, label="R-C = steal+IRQ")
    ax.set_xlabel("I_steal + I_IRQ per job (us)"); ax.set_ylabel("R - C per job (us)")
    ax.set_title("Delay-layer covariate attribution")
    ax.legend(fontsize=8)
    P.save(fig, figs, "fig_covariate_scatter")


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Model 3 figures")
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--dose-timeblocks", nargs="*", default=None,
                    help="sibling-arm runs at different --sibling-load (for the dose-response figure)")
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    P.apply_style()
    cfg = m3.load_config(args.config)
    root = Path(args.results_root) if args.results_root else HERE.parent / cfg["results"]["root"]
    tb_dir = root / args.timeblock
    figs = tb_dir / "figures"
    summ = tb_dir / "model3-summary.csv"
    if not summ.exists():
        print(f"no model3-summary.csv at {summ}; run analyze.py --timeblock {args.timeblock} first")
        return 1
    rows = P.read_csv(summ)
    infl = P.read_csv(tb_dir / "model3-inflation.csv")

    fig_c_distribution(tb_dir, cfg, rows, figs)
    fig_inflation_vs_u(tb_dir, cfg, infl, figs)
    fig_r_and_miss(tb_dir, cfg, rows, figs)
    fig_provisioning(tb_dir, cfg, infl, figs)
    fig_dose_response(cfg, root, args.dose_timeblocks, figs)
    fig_covariate(tb_dir, cfg, rows, figs)
    print(f"[plot] figures in {figs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
