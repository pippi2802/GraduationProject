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


def _load_cfg_scales(name):
    """Scales (P per scale) for a result set. Tagged sets like 'model3_sep'
    fall back to their base model's config ('model3')."""
    p = HERE / "models" / name / "config.yaml"
    if not p.exists():
        p = HERE / "models" / name.split("_")[0] / "config.yaml"
    cfg = yaml.safe_load(p.read_text())
    return {k: int(v) for k, v in cfg["scales"].items()}


def compare(a, b):
    """Overlay pooled CDFs of two result sets (e.g. sibling vs separate core)
    and print the C(a)/C(b) execution-time inflation per cell."""
    sa = _load_cfg_scales(a)
    ca = load_cells(a, sa)
    cb = load_cells(b, sa)
    figs = HERE / "results" / a / "figures"
    print(f"[compare] {a} vs {b}  (inflation = C_med[{a}] / C_med[{b}])")
    print(f"{'scale':6} {'U':>5} {'C50_a':>10} {'C50_b':>10} {'infl':>6} "
          f"{'miss_a':>7} {'miss_b':>7}")
    for scale in sa:
        A = ca.get(scale, {}); B = cb.get(scale, {})
        for u in sorted(set(A) & set(B)):
            ca_med = float(A[u].C.median()); cb_med = float(B[u].C.median())
            infl = ca_med / cb_med if cb_med else float("nan")
            print(f"{scale:6} {u:>5g} {ca_med:>10.0f} {cb_med:>10.0f} {infl:>6.2f} "
                  f"{float(A[u]['miss'].mean()):>7.3f} {float(B[u]['miss'].mean()):>7.3f}")
        for col, xlabel, fname in (("RoverD", "R / D", "cmp_RoverD"),
                                   ("alpha", "α = C/Q", "cmp_alpha")):
            va = [A[u][col].dropna().values for u in A]
            vb = [B[u][col].dropna().values for u in B]
            if not va or not vb:
                continue
            allA = np.sort(np.concatenate(va)); allB = np.sort(np.concatenate(vb))
            if len(allA) == 0 or len(allB) == 0:
                continue
            fig, ax = plt.subplots(figsize=(7.2, 4.6))
            ax.plot(allA, np.arange(1, len(allA) + 1) / len(allA),
                    color="#d62728", lw=2.4, label=a)
            ax.plot(allB, np.arange(1, len(allB) + 1) / len(allB),
                    color="#1f77b4", lw=2.4, label=b)
            ax.axvline(1.0, color="k", ls=":", lw=1.2, alpha=0.7)
            ax.text(1.0, 0.02, "limit = 1", color="k", fontsize=8,
                    rotation=90, va="bottom", ha="right", alpha=0.8)
            ax.set_xlabel(xlabel); ax.set_ylabel("P(X ≤ x)")
            ax.set_title(f"{xlabel} — {a} vs {b} ({scale}, all U pooled)")
            ax.set_ylim(0, 1.02); ax.grid(alpha=0.3)
            ax.legend(loc="lower right", fontsize=9, frameon=True)
            _save(fig, figs, f"{fname}_{scale}")
    print(f"[compare] figures in {figs}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "compare":
        return compare(args[1], args[2])
    if len(args) != 1:
        print("usage: result.py <model>  |  result.py compare <A> <B>"); return 2
    model = args[0]
    scales = _load_cfg_scales(model)
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
        if not summary.empty:
            over_u_figs(summary, scale, figs)
    print(f"[result] figures in {figs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
