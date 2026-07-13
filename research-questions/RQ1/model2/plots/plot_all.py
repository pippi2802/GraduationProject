#!/usr/bin/env python3
"""
plot_all.py — figure set for a Model 2 time-block.

  plot_all.py --variant intra --timeblock LABEL
  plot_all.py --variant inter --timeblock LABEL

Reads the per-variant summary (intra-summary.csv / inter-summary.csv from
analyze.py) plus per-cell per-job CSVs, and writes PNG+PDF to
results/<tb>/figures/. Linear axes; divergent cells annotated, not clipped.

INTRA (2a):  per-task R CCDF as k grows; victim p99/p99.9 vs k; container
             Delta_eff vs k (inner spread grows while server keeps Q); C vs R.
INTER (2b):  target alpha_eff vs neighbour load (flat = firewall holds; sloping =
             leak); target R percentiles vs load; cross-scale overlay; admission /
             over-subscribe arm; covariate correlation.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import model2lib as m2  # noqa: E402
sys.path.insert(0, str(HERE.parent.parent / "common"))
from rtmetrics import plotting as C  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


def _sd(cfg, scale):
    return cfg["scales"][scale]["dir"]


# ============================ INTRA ======================================== #
def intra_cell_dir(tb_dir, cfg, scale, u, k, split):
    return tb_dir / "intra" / _sd(cfg, scale) / m2.intra_cell_id(scale, u, k, split)



def fig_intra_ccdf(tb_dir, cfg, rows, figs):
    """Per-task R CCDF as k grows, one panel per (scale, U) of the equal split."""
    combos = sorted({(r["scale"], C.fnum(r["U"])) for r in rows if r["split"] == "equal"})
    for scale, u in combos:
        ks = sorted({int(r["k"]) for r in rows
                     if r["scale"] == scale and C.fnum(r["U"]) == u and r["split"] == "equal"})
        fig, ax = plt.subplots()
        cmap = plt.cm.viridis
        for i, k in enumerate(ks):
            cd = intra_cell_dir(tb_dir, cfg, scale, u, k, "equal")
            allR = []
            for ti in range(k):
                allR += [v for v in C.jobcol(cd, f"task{ti}.csv", "R_wall_us") if v is not None]
            C.ccdf(ax, allR, color=cmap(i / max(1, len(ks) - 1)), label=f"k={k}")
        ax.set_yscale("log")
        ax.set_xlabel("response time R (ms)"); ax.set_ylabel("P(R > x)")
        ax.set_title(f"Intra per-task R CCDF vs k — {C.SCALE_LABEL.get(scale, scale)} U={u:g}")
        ax.legend(fontsize=9)
        C.save(fig, figs, f"fig_intra_ccdf_{scale}_U{m2.u_label(u)}")


def fig_intra_victim_vs_k(tb_dir, cfg, rows, figs):
    """Victim-task p99/p99.9 vs k (victim split), one line per (scale,U)."""
    vic = [r for r in rows if r["split"] == "victim" and int(r["is_victim"]) == 1]
    if not vic:
        return
    groups = defaultdict(list)
    for r in vic:
        groups[(r["scale"], C.fnum(r["U"]))].append(r)
    fig, ax = plt.subplots()
    for (scale, u), rs in sorted(groups.items()):
        rs.sort(key=lambda x: int(x["k"]))
        ks = [int(x["k"]) for x in rs]
        p99 = [(C.fnum(x["R_p99"]) or 0) / 1000 for x in rs]
        p999 = [(C.fnum(x["R_p999"]) or 0) / 1000 for x in rs]
        col = C.SCALE_COLOR.get(scale)
        ax.plot(ks, p99, "o-", color=col, label=f"{scale} U={u:g} p99")
        ax.plot(ks, p999, "^--", color=col, alpha=0.6, label=f"{scale} U={u:g} p99.9")
    ax.set_xlabel("number of tasks k (shared budget)"); ax.set_ylabel("victim R (ms)")
    ax.set_title("Intra: victim-task tail vs contending task count")
    ax.legend(fontsize=8)
    C.save(fig, figs, "fig_intra_victim_tail_vs_k")


def fig_intra_delta_alpha_vs_k(tb_dir, cfg, rows, figs):
    """Container Delta_eff and alpha_eff vs k (server keeps Q; inner spread grows)."""
    # one representative row per (scale,U,k,split) carries the container-level values
    seen = {}
    for r in rows:
        key = (r["scale"], C.fnum(r["U"]), int(r["k"]), r["split"])
        seen.setdefault(key, r)
    for split in ("equal", "victim"):
        groups = defaultdict(list)
        for (scale, u, k, sp), r in seen.items():
            if sp != split:
                continue
            groups[(scale, u)].append((k, r))
        if not groups:
            continue
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
        for (scale, u), items in sorted(groups.items()):
            items.sort(key=lambda x: x[0])
            ks = [k for k, _ in items]
            delta = [(C.fnum(r["delta_eff_us"]) or 0) / 1000 for _, r in items]
            alpha = [C.fnum(r["container_alpha_eff"]) for _, r in items]
            col = C.SCALE_COLOR.get(scale)
            a1.plot(ks, delta, "o-", color=col, label=f"{scale} U={u:g}")
            a2.plot(ks, alpha, "s-", color=col, label=f"{scale} U={u:g}")
            a2.axhline(u, color=col, ls=":", alpha=0.4)
        a1.set_xlabel("k"); a1.set_ylabel("container Delta_eff (ms)")
        a1.set_title("inner spread grows with k"); a1.legend(fontsize=8)
        a2.set_xlabel("k"); a2.set_ylabel("container alpha_eff")
        a2.set_title("server keeps its budget (alpha ~= U)"); a2.legend(fontsize=8)
        fig.suptitle(f"Intra ({split} split): Delta_eff & alpha_eff vs k")
        C.save(fig, figs, f"fig_intra_delta_alpha_vs_k_{split}")


def fig_intra_c_vs_r(tb_dir, cfg, rows, figs):
    fig, ax = plt.subplots()
    for scale in ("tight", "soft"):
        xs = [C.fnum(r["C_p50"]) for r in rows if r["scale"] == scale]
        ys = [C.fnum(r["R_p50"]) for r in rows if r["scale"] == scale]
        pts = [(x / 1000, y / 1000) for x, y in zip(xs, ys) if x and y]
        if pts:
            ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=18,
                       color=C.SCALE_COLOR.get(scale), alpha=0.7,
                       label=C.SCALE_LABEL.get(scale, scale))
    lim = ax.get_xlim()
    ax.plot(lim, lim, "k:", alpha=0.5, label="R = C")
    ax.set_xlabel("per-task compute C p50 (ms)"); ax.set_ylabel("per-task wall R p50 (ms)")
    ax.set_title("Intra: compute vs wall per task"); ax.legend(fontsize=9)
    C.save(fig, figs, "fig_intra_C_vs_R")


# ============================ INTER ======================================== #
def inter_cell_dir(tb_dir, cfg, row):
    return (tb_dir / "inter" / _sd(cfg, row["scale"]) / row["arm"] / row["cell_id"])


def fig_inter_alpha_vs_load(tb_dir, cfg, rows, figs):
    tf = [r for r in rows if r["arm"] == "target_fixed"]
    if not tf:
        return
    for scale in sorted({r["scale"] for r in tf}):
        rs = sorted((r for r in tf if r["scale"] == scale),
                    key=lambda x: C.fnum(x["aggregate_neighbour_u"]))
        load = [C.fnum(r["aggregate_neighbour_u"]) for r in rs]
        alpha = [C.fnum(r["alpha_eff"]) for r in rs]
        theory = C.fnum(rs[0]["alpha_theory"]) if rs else None
        fig, ax = plt.subplots()
        ax.plot(load, alpha, "o-", color=C.SCALE_COLOR.get(scale), label="alpha_eff (target)")
        if theory is not None:
            ax.axhline(theory, color="k", ls="--", label=f"alpha=Q/P={theory:g} (theory)")
        for r in rs:
            if int(r["oversubscribe"]):
                ax.axvline(C.fnum(r["aggregate_neighbour_u"]), color="#888", ls=":", alpha=0.5)
        ax.set_xlabel("aggregate neighbour load (sum U)")
        ax.set_ylabel("target effective bandwidth alpha_eff")
        ax.set_title(f"Inter: target isolation vs neighbour load — {C.SCALE_LABEL.get(scale, scale)}\n"
                     "flat = firewall holds; sloping = bandwidth leak")
        ax.legend(fontsize=9)
        C.save(fig, figs, f"fig_inter_alpha_vs_load_{scale}")


def fig_inter_R_vs_load(tb_dir, cfg, rows, figs):
    tf = [r for r in rows if r["arm"] == "target_fixed"]
    for scale in sorted({r["scale"] for r in tf}):
        rs = sorted((r for r in tf if r["scale"] == scale),
                    key=lambda x: C.fnum(x["aggregate_neighbour_u"]))
        load = [C.fnum(r["aggregate_neighbour_u"]) for r in rs]
        fig, ax = plt.subplots()
        for key, style, lab in (("R_p50", "o-", "p50"), ("R_p99", "s-", "p99"),
                                ("R_p999", "^--", "p99.9")):
            ax.plot(load, [(C.fnum(r[key]) or 0) / 1000 for r in rs], style, label=lab)
        ax.set_xlabel("aggregate neighbour load (sum U)"); ax.set_ylabel("target R (ms)")
        ax.set_title(f"Inter: target R percentiles vs neighbour load — {C.SCALE_LABEL.get(scale, scale)}")
        ax.legend(fontsize=9)
        C.save(fig, figs, f"fig_inter_R_vs_load_{scale}")


def fig_inter_cross_scale(tb_dir, cfg, rows, figs):
    tf = [r for r in rows if r["arm"] == "target_fixed"]
    if not tf:
        return
    fig, ax = plt.subplots()
    for scale in sorted({r["scale"] for r in tf}):
        rs = sorted((r for r in tf if r["scale"] == scale),
                    key=lambda x: C.fnum(x["aggregate_neighbour_u"]))
        ax.plot([C.fnum(r["aggregate_neighbour_u"]) for r in rs],
                [(C.fnum(r["R_p99"]) or 0) / 1000 for r in rs], "o-",
                color=C.SCALE_COLOR.get(scale), label=C.SCALE_LABEL.get(scale, scale))
    ax.set_xlabel("aggregate neighbour load (sum U)"); ax.set_ylabel("target R p99 (ms)")
    ax.set_title("Inter cross-scale: persists at soft => bandwidth leak; fades => latency leak")
    ax.legend(fontsize=9)
    C.save(fig, figs, "fig_inter_cross_scale")


def fig_inter_admission(tb_dir, cfg, rows, figs):
    tf = [r for r in rows if r["arm"] == "target_fixed"]
    if not tf:
        return
    fig, ax = plt.subplots()
    for scale in sorted({r["scale"] for r in tf}):
        rs = sorted((r for r in tf if r["scale"] == scale),
                    key=lambda x: int(x["n_neighbours"]))
        req = [int(r["n_neighbours"]) for r in rs]
        adm = [C.fnum(r["neighbours_admitted"]) for r in rs]
        ax.plot(req, adm, "o-", color=C.SCALE_COLOR.get(scale), label=f"{scale} admitted")
    lim = ax.get_xlim()
    ax.plot(lim, lim, "k:", alpha=0.5, label="admitted = requested")
    ax.set_xlabel("neighbour reservations requested"); ax.set_ylabel("neighbours admitted")
    ax.set_title("Inter: admission / over-subscription behaviour")
    ax.legend(fontsize=9)
    C.save(fig, figs, "fig_inter_admission")


def fig_inter_target_sweep(tb_dir, cfg, rows, figs):
    nf = [r for r in rows if r["arm"] == "neighbour_fixed"]
    if not nf:
        return
    for scale in sorted({r["scale"] for r in nf}):
        rs = sorted((r for r in nf if r["scale"] == scale), key=lambda x: C.fnum(x["target_U"]))
        tu = [C.fnum(r["target_U"]) for r in rs]
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
        a1.plot(tu, [C.fnum(r["alpha_eff"]) for r in rs], "o-", color=C.SCALE_COLOR.get(scale), label="alpha_eff")
        a1.plot(tu, [C.fnum(r["alpha_theory"]) for r in rs], "k--", label="alpha=U (theory)")
        a1.set_xlabel("target U"); a1.set_ylabel("alpha_eff"); a1.set_title("target bandwidth under fixed neighbour load"); a1.legend(fontsize=8)
        a2.plot(tu, [(C.fnum(r["R_p99"]) or 0) / 1000 for r in rs], "s-", color=C.SCALE_COLOR.get(scale), label="R p99")
        a2.set_xlabel("target U"); a2.set_ylabel("target R p99 (ms)"); a2.set_title("target tail"); a2.legend(fontsize=8)
        fig.suptitle(f"Inter arm B (neighbour fixed) — {C.SCALE_LABEL.get(scale, scale)}")
        C.save(fig, figs, f"fig_inter_target_sweep_{scale}")


def fig_inter_covariate(tb_dir, cfg, rows, figs):
    fig, ax = plt.subplots()
    any_pts = False
    for scale in sorted({r["scale"] for r in rows}):
        xs, ys = [], []
        for r in (x for x in rows if x["scale"] == scale):
            cd = inter_cell_dir(tb_dir, cfg, r)
            R = C.jobcol(cd, "target.csv", "R_wall_us", cov=True)
            Cc = C.jobcol(cd, "target.csv", "C_cputime_us", cov=True)
            steal = C.jobcol(cd, "target.csv", "steal_us", cov=True)
            irq = C.jobcol(cd, "target.csv", "irq_us", cov=True)
            for i in range(min(len(R), len(Cc), len(steal), len(irq))):
                if None in (R[i], Cc[i], steal[i], irq[i]):
                    continue
                xs.append(steal[i] + irq[i]); ys.append(R[i] - Cc[i])
        if xs:
            any_pts = True
            ax.scatter(xs, ys, s=4, alpha=0.3, color=C.SCALE_COLOR.get(scale),
                       label=C.SCALE_LABEL.get(scale, scale))
    if not any_pts:
        plt.close(fig); return
    lim = ax.get_xlim()
    ax.plot(lim, lim, "k:", alpha=0.6, label="R-C = steal+IRQ")
    ax.set_xlabel("I_steal + I_IRQ per job (us)"); ax.set_ylabel("target R - C per job (us)")
    ax.set_title("Inter: target interference attribution")
    ax.legend(fontsize=9)
    C.save(fig, figs, "fig_inter_covariate_scatter")


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Model 2 figures")
    ap.add_argument("--variant", required=True, choices=["intra", "inter"])
    ap.add_argument("--timeblock", required=True)
    ap.add_argument("--results-root", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    C.apply_style()
    cfg = m2.load_config(args.config)
    root = Path(args.results_root) if args.results_root else HERE.parent / cfg["results"]["root"]
    tb_dir = root / args.timeblock
    figs = tb_dir / "figures"
    summary = tb_dir / (f"{args.variant}-summary.csv")
    if not summary.exists():
        print(f"no {summary.name} at {summary}; run analyze.py --variant {args.variant} first")
        return 1
    rows = C.read_csv(summary)

    if args.variant == "intra":
        fig_intra_ccdf(tb_dir, cfg, rows, figs)
        fig_intra_victim_vs_k(tb_dir, cfg, rows, figs)
        fig_intra_delta_alpha_vs_k(tb_dir, cfg, rows, figs)
        fig_intra_c_vs_r(tb_dir, cfg, rows, figs)
    else:
        fig_inter_alpha_vs_load(tb_dir, cfg, rows, figs)
        fig_inter_R_vs_load(tb_dir, cfg, rows, figs)
        fig_inter_cross_scale(tb_dir, cfg, rows, figs)
        fig_inter_admission(tb_dir, cfg, rows, figs)
        fig_inter_target_sweep(tb_dir, cfg, rows, figs)
        fig_inter_covariate(tb_dir, cfg, rows, figs)
    print(f"[plot] figures in {figs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
