#!/usr/bin/env python3
"""
plot_all.py — figure set for a Model 4 time-block (IRQ steering).

  plot_all.py --timeblock LABEL
  plot_all.py --timeblock LABEL --dose-timeblocks tb-light tb-medium tb-heavy

Reads the summaries from analyze.py (model4-summary.csv, model4-tail.csv) plus
per-cell per-job CSVs, and writes PNG+PDF to results/<tb>/figures/. Reuses the SHARED
plotting helpers in ../../common/rtmetrics/plotting.py.

Figures:
  1. R CCDF off vs on, per (scale, U), log tail axis          [the core figure]
  2. R tail (p99/p99.9/max) + deadline-miss rate vs U, off vs on, per scale
  3. Cross-scale overlay: on-arm R-p99 inflation tight vs soft [FADES at soft => delay-layer]
  4. Attribution: per-job I_IRQ vs (R-C) scatter (+ steal on a separate axis)
  5. Delta_eff / replenishment jitter vs U, off vs on
  6. Bounded-vs-heavy-tailed: mean-excess plot on the on-arm tail at fixed high U
  7. Dose-response: on-arm R-p99 vs --irq-load               [needs --dose-timeblocks]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import model4lib as m4  # noqa: E402
sys.path.insert(0, str(HERE.parents[1] / "common"))
from rtmetrics import plotting as P  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ARM_COLOR = {"off": "#1d4e89", "on": "#c1121f"}
ARM_LABEL = {"off": "off (IRQ steered away)", "on": "on (IRQ on RT core)"}


def _sd(cfg, scale):
    return cfg["scales"][scale]["dir"]


def cell_dir(tb_dir, cfg, arm, scale, u):
    return tb_dir / cfg["arms"][arm]["dir"] / _sd(cfg, scale) / f"U{m4.u_label(u)}"


# ============================ FIG 1 ======================================== #
def fig_r_ccdf(tb_dir, cfg, rows, figs):
    combos = sorted({(r["scale"], P.fnum(r["U"])) for r in rows})
    for scale, u in combos:
        fig, ax = plt.subplots()
        drew = False
        for arm in ("off", "on"):
            cd = cell_dir(tb_dir, cfg, arm, scale, u)
            Rvals = [v for v in P.jobcol(cd, "jobs.csv", "R_wall_us") if v is not None]
            if not Rvals:
                continue
            P.ccdf(ax, Rvals, color=ARM_COLOR[arm], label=ARM_LABEL[arm])
            drew = True
        if not drew:
            plt.close(fig); continue
        Pms = next((P.fnum(r["P_us"]) for r in rows
                    if r["scale"] == scale and P.fnum(r["U"]) == u), None)
        if Pms:
            ax.axvline(Pms / 1000, color="k", ls="--", alpha=0.6, label="deadline P")
        ax.set_yscale("log")
        ax.set_xlabel("response time R (ms)"); ax.set_ylabel("P(R > x)")
        ax.set_title(f"R CCDF off vs on — {P.SCALE_LABEL.get(scale, scale)} U={u:g}")
        ax.legend(fontsize=9)
        P.save(fig, figs, f"fig_r_ccdf_{scale}_U{m4.u_label(u)}")


# ============================ FIG 2 ======================================== #
def fig_tail_and_miss(tb_dir, cfg, rows, figs):
    for scale in sorted({r["scale"] for r in rows}):
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
        for arm in ("off", "on"):
            rs = sorted((r for r in rows if r["scale"] == scale and r["arm"] == arm),
                        key=lambda x: P.fnum(x["U"]))
            if not rs:
                continue
            u = [P.fnum(r["U"]) for r in rs]
            a1.plot(u, [(P.fnum(r["R_p99"]) or 0) / 1000 for r in rs], "o-",
                    color=ARM_COLOR[arm], label=f"{ARM_LABEL[arm]} p99")
            a1.plot(u, [(P.fnum(r["R_p999"]) or 0) / 1000 for r in rs], "^--",
                    color=ARM_COLOR[arm], alpha=0.55, label=f"{ARM_LABEL[arm]} p99.9")
            a2.plot(u, [P.fnum(r["miss_rate"]) for r in rs], "o-",
                    color=ARM_COLOR[arm], label=ARM_LABEL[arm])
        a1.set_xlabel("U"); a1.set_ylabel("R tail (ms)"); a1.set_title("R p99 / p99.9"); a1.legend(fontsize=8)
        a2.set_xlabel("U"); a2.set_ylabel("deadline-miss rate"); a2.set_title("miss rate"); a2.legend(fontsize=8)
        fig.suptitle(f"Model 4 R-tail & miss vs U — {P.SCALE_LABEL.get(scale, scale)}")
        P.save(fig, figs, f"fig_tail_miss_vs_u_{scale}")


# ============================ FIG 3 ======================================== #
def fig_cross_scale(tb_dir, cfg, tail, figs):
    if not tail:
        return
    fig, ax = plt.subplots()
    for scale in sorted({r["scale"] for r in tail}):
        rs = sorted((r for r in tail if r["scale"] == scale), key=lambda x: P.fnum(x["U"]))
        ax.plot([P.fnum(r["U"]) for r in rs], [P.fnum(r["R_p99_inflation"]) for r in rs], "o-",
                color=P.SCALE_COLOR.get(scale), label=P.SCALE_LABEL.get(scale, scale))
    ax.axhline(1.0, color="k", ls=":", alpha=0.6, label="no inflation")
    ax.set_xlabel("U"); ax.set_ylabel("on/off R-p99 inflation")
    ax.set_title("Cross-scale: IRQ tail inflation\nFADES at soft => delay-layer break (mirror of Model 3)")
    ax.legend(fontsize=9)
    P.save(fig, figs, "fig_cross_scale_inflation")


# ============================ FIG 4 ======================================== #
def fig_attribution(tb_dir, cfg, rows, figs):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
    any1 = any2 = False
    for scale in sorted({r["scale"] for r in rows}):
        for arm in ("off", "on"):
            xs_irq, ys, xs_steal = [], [], []
            for r in (x for x in rows if x["scale"] == scale and x["arm"] == arm):
                cd = cell_dir(tb_dir, cfg, arm, scale, P.fnum(r["U"]))
                Rc = P.jobcol(cd, "jobs.csv", "R_wall_us", cov=True)
                Cc = P.jobcol(cd, "jobs.csv", "C_cputime_us", cov=True)
                irq = P.jobcol(cd, "jobs.csv", "irq_us", cov=True)
                steal = P.jobcol(cd, "jobs.csv", "steal_us", cov=True)
                for i in range(min(len(Rc), len(Cc), len(irq), len(steal))):
                    if None in (Rc[i], Cc[i], irq[i], steal[i]):
                        continue
                    xs_irq.append(irq[i]); ys.append(Rc[i] - Cc[i]); xs_steal.append(steal[i])
            if xs_irq:
                any1 = True
                a1.scatter(xs_irq, ys, s=4, alpha=0.3, color=ARM_COLOR[arm],
                           label=f"{ARM_LABEL[arm]} ({scale})")
            if xs_steal:
                any2 = True
                a2.scatter(xs_steal, ys, s=4, alpha=0.3, color=ARM_COLOR[arm],
                           label=f"{ARM_LABEL[arm]} ({scale})")
    if not any1:
        plt.close(fig); return
    a1.set_xlabel("per-job I_IRQ (us)"); a1.set_ylabel("R - C per job (us)")
    a1.set_title("tail attributed to IRQ (positive)"); a1.legend(fontsize=8)
    a2.set_xlabel("per-job steal (us)"); a2.set_ylabel("R - C per job (us)")
    a2.set_title("steal is NOT the cause (flat)"); a2.legend(fontsize=8)
    fig.suptitle("Model 4: delay-layer attribution — IRQ vs steal")
    P.save(fig, figs, "fig_irq_attribution")


# ============================ FIG 5 ======================================== #
def fig_delta_eff(tb_dir, cfg, tail, figs):
    if not tail:
        return
    for scale in sorted({r["scale"] for r in tail}):
        rs = sorted((r for r in tail if r["scale"] == scale), key=lambda x: P.fnum(x["U"]))
        u = [P.fnum(r["U"]) for r in rs]
        fig, ax = plt.subplots()
        ax.plot(u, [(P.fnum(r["delta_eff_us_off"]) or 0) / 1000 for r in rs], "o-",
                color=ARM_COLOR["off"], label="Delta_eff off")
        ax.plot(u, [(P.fnum(r["delta_eff_us_on"]) or 0) / 1000 for r in rs], "s-",
                color=ARM_COLOR["on"], label="Delta_eff on")
        ax.set_xlabel("U"); ax.set_ylabel("Delta_eff = max dispatch delay (ms)")
        ax.set_title(f"Replenishment/dispatch jitter vs U — {P.SCALE_LABEL.get(scale, scale)}")
        ax.legend(fontsize=9)
        P.save(fig, figs, f"fig_delta_eff_vs_u_{scale}")


# ============================ FIG 6 ======================================== #
def _mean_excess(vals):
    xs = sorted(v for v in vals if v is not None)
    if len(xs) < 20:
        return [], []
    us, es = [], []
    n = len(xs)
    # thresholds from p50..p99.5
    for q in [i / 100 for i in range(50, 100)] + [0.995]:
        u = xs[min(n - 1, int(q * n))]
        exc = [x - u for x in xs if x > u]
        if len(exc) >= 5:
            us.append(u / 1000); es.append((sum(exc) / len(exc)) / 1000)
    return us, es


def fig_mean_excess(tb_dir, cfg, rows, figs):
    u_hi = cfg["irq_source"].get("dose_response_utilization", 0.9)
    fig, ax = plt.subplots()
    drew = False
    for scale in sorted({r["scale"] for r in rows}):
        # nearest available U to u_hi for the on arm
        us_here = sorted({P.fnum(r["U"]) for r in rows if r["scale"] == scale and r["arm"] == "on"})
        if not us_here:
            continue
        u = min(us_here, key=lambda x: abs(x - u_hi))
        cd = cell_dir(tb_dir, cfg, "on", scale, u)
        R = [v for v in P.jobcol(cd, "jobs.csv", "R_wall_us") if v is not None]
        xs, es = _mean_excess(R)
        if xs:
            drew = True
            ax.plot(xs, es, "o-", color=P.SCALE_COLOR.get(scale),
                    label=f"{P.SCALE_LABEL.get(scale, scale)} U={u:g}")
    if not drew:
        plt.close(fig); return
    ax.set_xlabel("threshold u (ms)"); ax.set_ylabel("mean excess E[R-u | R>u] (ms)")
    ax.set_title("Bounded-vs-heavy-tailed (on arm)\nflat/decreasing => bounded; rising => heavy-tailed")
    ax.legend(fontsize=9)
    P.save(fig, figs, "fig_mean_excess_on")


# ============================ FIG 7 ======================================== #
def fig_dose_response(cfg, root, dose_tbs, figs):
    if not dose_tbs:
        return
    u_target = cfg["irq_source"]["dose_response_utilization"]
    per_scale = {}   # scale -> [(load, R_p99_on)]
    order = list(cfg["irq_source"]["levels"].keys())
    for tbname in dose_tbs:
        summ = root / tbname / "model4-summary.csv"
        if not summ.exists():
            print(f"[plot] dose: missing {summ}; skip"); continue
        # infer this run's load from the summary filename set is not stored; read
        # the arm=on rows at u_target and tag by the run's irq_load via summary sidecar
        loadtag = _infer_load(root / tbname)
        for r in P.read_csv(summ):
            if r["arm"] != "on" or abs(P.fnum(r["U"]) - u_target) > 1e-9:
                continue
            per_scale.setdefault(r["scale"], []).append((loadtag, P.fnum(r["R_p99"])))
    if not per_scale:
        return
    fig, ax = plt.subplots()
    for scale, pts in sorted(per_scale.items()):
        pts = [p for p in pts if p[0] is not None]
        pts.sort(key=lambda p: order.index(p[0]) if p[0] in order else 99)
        ax.plot([p[0] for p in pts], [(p[1] or 0) / 1000 for p in pts], "o-",
                color=P.SCALE_COLOR.get(scale), label=P.SCALE_LABEL.get(scale, scale))
    ax.set_xlabel("--irq-load"); ax.set_ylabel("on-arm R p99 (ms)")
    ax.set_title(f"Dose-response: R tail vs IRQ load @ U={u_target:g}")
    ax.legend(fontsize=9)
    P.save(fig, figs, "fig_dose_response")


def _infer_load(tb_dir: Path):
    """Read the irq_load from a run's summary-<arm>-<load>.json filename."""
    for p in tb_dir.glob("summary-on-*.json"):
        return p.stem.replace("summary-on-", "")
    return None


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Model 4 figures")
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--dose-timeblocks", nargs="*", default=None,
                    help="on-arm runs at different --irq-load (for the dose-response figure)")
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    P.apply_style()
    cfg = m4.load_config(args.config)
    root = Path(args.results_root) if args.results_root else HERE.parent / cfg["results"]["root"]
    tb_dir = root / args.timeblock
    figs = tb_dir / "figures"
    summ = tb_dir / "model4-summary.csv"
    if not summ.exists():
        print(f"no model4-summary.csv at {summ}; run analyze.py --timeblock {args.timeblock} first")
        return 1
    rows = P.read_csv(summ)
    tail = P.read_csv(tb_dir / "model4-tail.csv")

    fig_r_ccdf(tb_dir, cfg, rows, figs)
    fig_tail_and_miss(tb_dir, cfg, rows, figs)
    fig_cross_scale(tb_dir, cfg, tail, figs)
    fig_attribution(tb_dir, cfg, rows, figs)
    fig_delta_eff(tb_dir, cfg, tail, figs)
    fig_mean_excess(tb_dir, cfg, rows, figs)
    fig_dose_response(cfg, root, args.dose_timeblocks, figs)
    print(f"[plot] figures in {figs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
