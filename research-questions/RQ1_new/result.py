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

HERE = Path(__file__).resolve().parent


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
    fig, ax = plt.subplots(figsize=(6, 4))
    us = sorted(cells)
    colors = {u: cm.viridis(i / max(1, len(us) - 1)) for i, u in enumerate(us)}
    for u in us:
        v = np.sort(cells[u][col].dropna().values)
        if len(v) == 0:
            continue
        y = np.arange(1, len(v) + 1) / len(v)
        ax.plot(v, y, label=f"U={u:g}", color=colors[u], lw=1.3)
    if mark_one:
        ax.axvline(1.0, color="red", ls=":", lw=1, alpha=0.7)
    ax.set_xlabel(xlabel); ax.set_ylabel("P(X ≤ x)"); ax.set_title(title)
    ax.set_ylim(0, 1.02); ax.grid(alpha=0.3); ax.legend(fontsize=7, ncol=2)
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
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(d.U, d.RoverD_p99, "o-", color="C0", label="R/D p99")
    ax.plot(d.U, d.alpha_p99, "s-", color="C1", label="alpha=C/Q p99")
    ax.plot(d.U, d.delta_p99, "^-", color="C2", label="delta=(R-C)/bound p99")
    ax.axhline(1.0, color="red", ls=":", lw=1, alpha=0.7, label="bound = 1")
    ax.set_xlabel("U"); ax.set_ylabel("normalized (p99)")
    ax.set_title(f"margins vs U ({scale}) — above 1 = break"); ax.grid(alpha=0.3)
    ax.legend(fontsize=7)
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

    for scale in scales:
        c = cells.get(scale, {})
        if c:
            cdf_fig(c, "RoverD", "R / D", f"CDF of R/D ({scale})", figs, f"cdf_RoverD_{scale}")
            cdf_fig(c, "delta", "(R−C)/bound", f"CDF of Δ ({scale})", figs, f"cdf_delta_{scale}", mark_one=False)
            cdf_fig(c, "alpha", "α = C/Q", f"CDF of α ({scale})", figs, f"cdf_alpha_{scale}")
        if not summary.empty:
            over_u_figs(summary, scale, figs)
    print(f"[result] figures in {figs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
