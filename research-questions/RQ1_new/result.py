#!/usr/bin/env python3
"""
result.py <model> — the five RQ1 figures + a summary CSV, from the collected data.

Reads results/<model>/<scale>/U<u>/jobs.csv and writes, per scale (soft AND tight),
into results/<model>/figures/:
  1. cdf_RoverD_<scale>   CDF of R/D            (mark deadline at 1)
  2. cdf_delta_<scale>    CDF of (R-C)/bound
  3. cdf_alpha_<scale>    CDF of C/Q            (mark budget at 1)
  4. abs_RC_vs_U_<scale>  |R| and |C| (p50,p99) vs U
  5. margin_vs_U_<scale>  p99 of R/D, alpha, delta vs U (break line at 1)
plus results/<model>/summary.csv (one row per cell, same schema for every model).

Definitions: D=P, alpha=C/Q, bound=2(P-Q), delta=(R-C)/bound.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent

# Qualitative, high-contrast palette + distinct markers so each U curve is
# separable both in colour AND in black/white (sequential viridis made adjacent
# U levels indistinguishable). Cycled if there are more curves than entries.
_PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
            "#17becf", "#8c564b", "#e377c2", "#bcbd22", "#7f7f7f"]
_MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*", "<", ">"]


def _style(i):
    return _PALETTE[i % len(_PALETTE)], _MARKERS[i % len(_MARKERS)]


def load_cells(model, scales):
    """{scale: {u: DataFrame(R/D, alpha, delta, R, C, miss)}}."""
    base = HERE / "results" / model
    out = {s: {} for s in scales}
    for jobs in sorted(base.glob("*/U*/jobs.csv")):
        scale = jobs.parent.parent.name
        if scale not in scales:
            continue
        u = float(jobs.parent.name[1:])           # "U0.5" -> 0.5
        P = scales[scale]; Q = round(u * P); bound = max(1, 2 * (P - Q))
        try:
            df = pd.read_csv(jobs, comment="#")
        except Exception:
            continue
        if df.empty or "R_wall_us" not in df:
            continue
        df = df.dropna(subset=["R_wall_us", "C_cputime_us"])
        out[scale][u] = pd.DataFrame({
            "R": df["R_wall_us"], "C": df["C_cputime_us"],
            "RoverD": df["R_wall_us"] / P,
            "alpha": df["C_cputime_us"] / Q,
            "delta": (df["R_wall_us"] - df["C_cputime_us"]) / bound,
            "miss": df.get("deadline_miss", 0),
        })
    return out


def _save(fig, figs, name):
    figs.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(figs / f"{name}.{ext}", bbox_inches="tight", dpi=140)
    plt.close(fig)


def cdf_fig(cells, col, xlabel, title, figs, name, mark_one=True):
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    us = sorted(cells)
    for i, u in enumerate(us):
        v = np.sort(cells[u][col].dropna().values)
        if len(v) == 0:
            continue
        y = np.arange(1, len(v) + 1) / len(v)
        color, marker = _style(i)
        # sparse markers (every ~1/8th of the curve) so lines are separable in B/W
        step = max(1, len(v) // 8)
        ax.plot(v, y, label=f"U={u:g}", color=color, lw=1.8,
                marker=marker, markevery=step, markersize=5, markeredgecolor="white",
                markeredgewidth=0.4)
    if mark_one:
        ax.axvline(1.0, color="red", ls=":", lw=1.4, alpha=0.8, zorder=1)
        ax.text(1.0, 0.02, "deadline", color="red", fontsize=8,
                rotation=90, va="bottom", ha="right", alpha=0.8)
    ax.set_xlabel(xlabel); ax.set_ylabel("P(X ≤ 1)"); ax.set_title(title)
    ax.set_ylim(0, 1.02); ax.grid(alpha=0.3)
    # legend OUTSIDE the axes (right), ordered high->low U to match curve order
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], title="utilisation",
              fontsize=9, title_fontsize=9, loc="center left",
              bbox_to_anchor=(1.01, 0.5), frameon=True)
    _save(fig, figs, name)


def cdf_pooled_fig(cells, col, xlabel, title, figs, name, mark_one=True):
    """ONE CDF pooling every U into a single curve. Valid because the metric is
    normalized (R/D, alpha=C/Q, delta) — each job is already on the same 0-1 scale,
    so the pooled curve answers the headline: across the whole U range, what
    fraction of jobs stayed under the break line (=1)?"""
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    arrs = [cells[u][col].dropna().values for u in cells]
    allv = np.sort(np.concatenate([a for a in arrs if len(a)])) if arrs else np.array([])
    if len(allv):
        y = np.arange(1, len(allv) + 1) / len(allv)
        ax.plot(allv, y, color="#1f77b4", lw=2.4, label="all U pooled")
        if mark_one:
            frac = float(np.mean(allv <= 1.0))
            ax.text(0.03, 0.97, f"P(≤ 1) = {frac:.3f}", transform=ax.transAxes,
                    va="top", ha="left", fontsize=10,
                    bbox=dict(boxstyle="round", fc="white", ec="0.7"))
    if mark_one:
        ax.axvline(1.0, color="red", ls=":", lw=1.4, alpha=0.8)
        ax.text(1.0, 0.02, "break (=1)", color="red", fontsize=8,
                rotation=90, va="bottom", ha="right", alpha=0.8)
    ax.set_xlabel(xlabel); ax.set_ylabel("P(X ≤ x)"); ax.set_title(title)
    ax.set_ylim(0, 1.02); ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="lower right")
    _save(fig, figs, name)


def over_u_figs(summary_df, scale, figs):
    d = summary_df[(summary_df.scale == scale) & (summary_df.n > 0)].sort_values("U")
    if d.empty:
        return
    # 4. absolute R, C
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(d.U, d.R_p50, "o-", color="C0", label="R p50")
    ax.plot(d.U, d.R_p99, "o--", color="C0", alpha=0.7, label="R p99")
    ax.plot(d.U, d.C_p50, "s-", color="C1", label="C p50")
    ax.plot(d.U, d.C_p99, "s--", color="C1", alpha=0.7, label="C p99")
    ax.set_yscale("log"); ax.set_xlabel("U"); ax.set_ylabel("µs (log)")
    ax.set_title(f"|R| and |C| vs U ({scale})"); ax.grid(alpha=0.3); ax.legend(fontsize=7)
    _save(fig, figs, f"abs_RC_vs_U_{scale}")
    # 5. margins
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    ax.plot(d.U, d.RoverD_p99, "o-", color="#1f77b4", lw=2, ms=7, label="R/D (deadline)")
    ax.plot(d.U, d.alpha_p99, "s-", color="#ff7f0e", lw=2, ms=7, label="α = C/Q (bandwidth)")
    ax.plot(d.U, d.delta_p99, "^-", color="#2ca02c", lw=2, ms=7, label="δ = (R−C)/bound (delay)")
    ax.axhline(1.0, color="red", ls=":", lw=1.4, alpha=0.8)
    ax.text(d.U.min(), 1.005, "break line (=1)", color="red", fontsize=8, va="bottom")
    ax.set_ylim(0, max(1.1, float(d[["RoverD_p99", "alpha_p99", "delta_p99"]].max().max()) * 1.1))
    ax.set_xlabel("reserved utilisation  U = Q/P"); ax.set_ylabel("normalised margin (p99)")
    ax.set_title(f"margins vs U ({scale}) — above 1 = guarantee breaks")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=True)
    _save(fig, figs, f"margin_vs_U_{scale}")


def summarize(cells_by_scale):
    rows = []
    for scale, cells in cells_by_scale.items():
        for u, df in cells.items():
            if df.empty:
                continue
            rows.append({
                "model": None, "scale": scale, "U": u, "n": len(df),
                "miss_rate": round(float(df["miss"].mean()), 5),
                "R_p50": df.R.quantile(.50), "R_p99": df.R.quantile(.99),
                "R_p999": df.R.quantile(.999), "R_max": df.R.max(),
                "C_p50": df.C.quantile(.50), "C_p99": df.C.quantile(.99),
                "RoverD_p50": df.RoverD.quantile(.50), "RoverD_p99": df.RoverD.quantile(.99),
                "RoverD_p999": df.RoverD.quantile(.999),
                "alpha_p50": df.alpha.quantile(.50), "alpha_p99": df.alpha.quantile(.99),
                "delta_p50": df.delta.quantile(.50), "delta_p99": df.delta.quantile(.99),
            })
    return pd.DataFrame(rows)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: result.py <model>"); return 2
    model = sys.argv[1]
    cfg = yaml.safe_load((HERE / "models" / model / "config.yaml").read_text())
    scales = {k: int(v) for k, v in cfg["scales"].items()}
    base = HERE / "results" / model
    figs = base / "figures"

    cells = load_cells(model, scales)
    summary = summarize(cells)
    if not summary.empty:
        summary["model"] = model
        summary.to_csv(base / "summary.csv", index=False)
        print(f"[result] wrote {base/'summary.csv'} ({len(summary)} cells)")
    elif (base / "summary.csv").exists():
        # raw jobs.csv were pruned (only summary survived): still redraw the vs-U
        # figures from the saved summary. CDFs need the per-job data and are skipped.
        summary = pd.read_csv(base / "summary.csv")
        print(f"[result] raw jobs.csv absent — redrawing vs-U figures from "
              f"existing summary.csv ({len(summary)} cells); CDFs need raw data.")

    for scale in scales:
        c = cells.get(scale, {})
        if c:
            cdf_fig(c, "RoverD", "R / D", f"CDF of normalized Response Time ({scale})", figs, f"cdf_RoverD_{scale}")
            cdf_fig(c, "delta", "(R−C)/bound", f"CDF of normalized Δ ({scale})", figs, f"cdf_delta_{scale}", mark_one=False)
            cdf_fig(c, "alpha", "α = C/Q", f"CDF of normalized α ({scale})", figs, f"cdf_alpha_{scale}")
            # pooled "all U" CDFs — the one-line headline per metric
            cdf_pooled_fig(c, "RoverD", "R / D", f"CDF of R/D — all U pooled ({scale})", figs, f"cdf_RoverD_all_{scale}")
            cdf_pooled_fig(c, "delta", "(R−C)/bound", f"CDF of Δ — all U pooled ({scale})", figs, f"cdf_delta_all_{scale}", mark_one=False)
            cdf_pooled_fig(c, "alpha", "α = C/Q", f"CDF of α — all U pooled ({scale})", figs, f"cdf_alpha_all_{scale}")
        if not summary.empty:
            over_u_figs(summary, scale, figs)
    print(f"[result] figures in {figs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
