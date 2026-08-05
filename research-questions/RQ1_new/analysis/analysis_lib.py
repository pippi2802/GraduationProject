"""analysis_lib.py -- helper functions for analysis_notebook.ipynb.

Kept separate from the notebook on purpose: the notebook should read like a
report (one section per question, a couple of function calls, the output),
not a wall of plotting boilerplate. All the pandas/matplotlib mechanics live
here.

Definitions (same as result.py, restated here so this module is
self-contained):
  D (deadline)  = P (period)
  Q (budget)    = round(U * P)
  bound         = max(1, 2*(P - Q))          -- normalizer for delta
  alpha         = C_cputime_us / Q            -- budget-overrun ratio
  delta         = (R_wall_us - C_cputime_us) / bound
  R/D           = R_wall_us / P
Raw (non-normalized) counterparts, requested alongside the normalized ones:
  C_cputime_us itself (raw execution time)
  R_wall_us - C_cputime_us  (raw added latency, microseconds)
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
CLEAN = HERE / "clean_data"

# scale -> period (P), microseconds. Same values as every model's config.yaml.
PERIOD_US = {"tight": 10_000, "soft": 100_000}

# Qualitative, colorblind-considered, high-contrast palette -- reused as-is
# from result.py (already validated there for this exact purpose: distinct
# hue AND marker per U series, order fixed/not cycled arbitrarily).
PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
           "#17becf", "#8c564b", "#e377c2", "#bcbd22", "#7f7f7f"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*", "<", ">"]


def style(i):
    return PALETTE[i % len(PALETTE)], MARKERS[i % len(MARKERS)]


def load_model(model: str) -> pd.DataFrame:
    """Load clean_data/<model>.csv and attach derived columns. Empty
    DataFrame (with a printed warning) if the model has nothing valid
    pooled yet -- see clean_data/MANIFEST.json for why."""
    f = CLEAN / f"{model}.csv"
    if not f.exists():
        print(f"[analysis_lib] {model}: no clean_data/{model}.csv -- "
              f"nothing valid pooled yet (check clean_data/MANIFEST.json)")
        return pd.DataFrame()
    df = pd.read_csv(f)
    df["P"] = df["scale"].map(PERIOD_US)
    df["Q"] = (df["U"] * df["P"]).round()
    df["bound"] = (2 * (df["P"] - df["Q"])).clip(lower=1)
    df["alpha"] = df["C_cputime_us"] / df["Q"]
    df["delta"] = (df["R_wall_us"] - df["C_cputime_us"]) / df["bound"]
    df["RoverD"] = df["R_wall_us"] / df["P"]
    df["added_latency_us"] = df["R_wall_us"] - df["C_cputime_us"]  # raw delta
    return df


# ---------------------------------------------------------------------------
# Section A: pooled-dataset-level
# ---------------------------------------------------------------------------

def descriptives_table(df: pd.DataFrame) -> pd.DataFrame:
    """Basic descriptives for R and C, per scale. A table, not a plot --
    exact numbers are more useful here than a picture."""
    rows = []
    for scale, g in df.groupby("scale"):
        for col, label in [("R_wall_us", "R (response)"), ("C_cputime_us", "C (execution)")]:
            s = g[col]
            rows.append({
                "scale": scale, "metric": label, "n": len(s),
                "mean": round(s.mean(), 1), "std": round(s.std(), 1),
                "min": round(s.min(), 1), "p50": round(s.median(), 1),
                "p95": round(s.quantile(.95), 1), "p99": round(s.quantile(.99), 1),
                "p999": round(s.quantile(.999), 1), "max": round(s.max(), 1),
            })
    return pd.DataFrame(rows)


def distribution_over_u(df: pd.DataFrame, col: str, ylabel: str, title: str, ax=None):
    """Boxplot of `col` at each U, one panel per scale -- shows how the
    distribution's shape (not just its median) evolves across the sweep.
    Whiskers at 1.5xIQR, outliers shown faint so they don't dominate."""
    scales = sorted(df["scale"].unique(), key=lambda s: PERIOD_US[s])
    fig, axes = plt.subplots(1, len(scales), figsize=(6 * len(scales), 4), squeeze=False)
    for ax, scale in zip(axes[0], scales):
        g = df[df.scale == scale]
        us = sorted(g["U"].unique())
        data = [g[g.U == u][col].values for u in us]
        bp = ax.boxplot(data, positions=range(len(us)), widths=0.6,
                         showfliers=True, flierprops=dict(marker=".", markersize=2, alpha=0.25),
                         patch_artist=True)
        for patch in bp["boxes"]:
            patch.set_facecolor(PALETTE[0]); patch.set_alpha(0.35); patch.set_edgecolor(PALETTE[0])
        for med in bp["medians"]:
            med.set_color(PALETTE[1]); med.set_linewidth(2)
        ax.set_xticks(range(len(us))); ax.set_xticklabels([f"{u:g}" for u in us])
        ax.set_xlabel("U"); ax.set_ylabel(ylabel); ax.set_title(f"{title} -- {scale}")
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    return fig


def budget_overrun_table(df: pd.DataFrame) -> pd.DataFrame:
    """Fraction of jobs where execution alone (C) exceeds the reservation's
    own budget (Q) -- alpha > 1 -- independent of whether the job also went
    on to miss its deadline. Per scale/U."""
    rows = []
    for (scale, u), g in df.groupby(["scale", "U"]):
        rows.append({
            "scale": scale, "U": u, "n": len(g),
            "overrun_rate": round((g["alpha"] > 1).mean(), 4),
            "alpha_p50": round(g["alpha"].median(), 3),
            "alpha_p99": round(g["alpha"].quantile(.99), 3),
            "alpha_max": round(g["alpha"].max(), 3),
        })
    return pd.DataFrame(rows).sort_values(["scale", "U"])


def round_stability_table(model: str) -> pd.DataFrame:
    """Per-round miss_rate/C_p50 side by side, straight from the INCLUDED
    rounds' raw jobs.csv (not the pooled file) -- this is the exact check
    that caught the coin-flip bug earlier: a round whose numbers don't match
    its siblings at the same U is the tell. Embedded here as a standing QA
    check, not a one-off script, since the pooled CSV alone can't show this
    (pooling is precisely what hides it)."""
    import build_clean_dataset as bcd
    rows_status = bcd.ROUND_STATUS.get(model, [])
    included = [r for r, ok, _ in rows_status if ok]
    frames = []
    for r in included:
        d = bcd.load_round(model, r)
        if d.empty:
            continue
        d["P"] = d["scale"].map(PERIOD_US)
        d["Q"] = (d["U"] * d["P"]).round()
        d["C_cputime_us"] = d["C_cputime_us"]
        g = d.groupby(["scale", "U"]).agg(
            n=("deadline_miss", "size"),
            miss_rate=("deadline_miss", "mean"),
            C_p50=("C_cputime_us", "median"),
        ).reset_index()
        g["round"] = r
        frames.append(g)
    if not frames:
        return pd.DataFrame()
    long = pd.concat(frames, ignore_index=True)
    piv_miss = long.pivot_table(index=["scale", "U"], columns="round", values="miss_rate")
    piv_c = long.pivot_table(index=["scale", "U"], columns="round", values="C_p50")
    piv_c.columns = [f"C_p50[{c}]" for c in piv_c.columns]
    return piv_miss.join(piv_c)


def longest_miss_run_table(model: str) -> pd.DataFrame:
    """Longest run of CONSECUTIVE missed deadlines, per scale/U -- a
    temporal statistic, so (per result.py's pool() docstring) computed
    per-round on that round's own job_index-ordered sequence, then MAXED
    across included rounds -- never concatenate raw sequences across rounds
    for this one, that would fabricate a run spanning a boundary between two
    unrelated collection times that never actually happened."""
    import build_clean_dataset as bcd
    rows_status = bcd.ROUND_STATUS.get(model, [])
    included = [r for r, ok, _ in rows_status if ok]
    best = {}
    for r in included:
        d = bcd.load_round(model, r)
        if d.empty:
            continue
        for (scale, u), g in d.groupby(["scale", "U"]):
            g = g.sort_values("job_index")
            miss = g["deadline_miss"].values
            run = maxrun = 0
            for m in miss:
                run = run + 1 if m else 0
                maxrun = max(maxrun, run)
            key = (scale, u)
            best[key] = max(best.get(key, 0), maxrun)
    rows = [{"scale": s, "U": u, "longest_consecutive_miss_run": v} for (s, u), v in best.items()]
    return pd.DataFrame(rows).sort_values(["scale", "U"])


def preemption_table(df: pd.DataFrame, threshold_us: float = 100.0) -> pd.DataFrame:
    """How many jobs were preempted mid-execution, and for how long -- per
    scale/U. Unlike longest_miss_run_table this is safe to compute on the
    POOLED dataframe directly: mid_job_preempt_us is an independent per-job
    measurement, not a temporal sequence, so pooling across rounds doesn't
    fabricate anything here.

    A tight duration distribution (small std relative to the mean) across
    many affected jobs is the signature of a recurring EXTERNAL event with a
    near-fixed cost (e.g. matches another process's own period/budget) --
    worth comparing mean_preempt_us against Q for any fixed-intensity
    co-runner in the model (co_runners.competitor.u * P) to check for exactly
    that. A wide/noisy distribution instead suggests generic contention
    rather than one specific recurring cause."""
    rows = []
    for (scale, u), g in df.groupby(["scale", "U"]):
        affected = g[g["mid_job_preempt_us"] > threshold_us]
        row = {"scale": scale, "U": u, "n": len(g), "n_affected": len(affected),
               "pct_affected": round(100 * len(affected) / len(g), 2)}
        if len(affected):
            row.update({
                "mean_preempt_us": round(affected["mid_job_preempt_us"].mean(), 1),
                "std_preempt_us": round(affected["mid_job_preempt_us"].std(), 1),
                "median_preempt_us": round(affected["mid_job_preempt_us"].median(), 1),
                "max_preempt_us": round(affected["mid_job_preempt_us"].max(), 1),
            })
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["scale", "U"])


def safe_margin_table(df: pd.DataFrame) -> pd.DataFrame:
    """The empirical 'how far can you provision' answer: largest U at which
    p99 / p999 of R/D still stays under 1 (deadline). Interpolated linearly
    between the bracketing U values, same method as result.py's
    provisioning_table()."""
    rows = []
    for scale, g in df.groupby("scale"):
        per_u = g.groupby("U")["RoverD"].agg(p99=lambda s: s.quantile(.99),
                                               p999=lambda s: s.quantile(.999)).reset_index()
        per_u = per_u.sort_values("U")
        row = {"scale": scale}
        for col in ["p99", "p999"]:
            u_vals = per_u["U"].values; r_vals = per_u[col].values
            u_safe = None
            for i in range(len(u_vals) - 1):
                if r_vals[i] <= 1 and r_vals[i + 1] > 1:
                    frac = (1 - r_vals[i]) / (r_vals[i + 1] - r_vals[i])
                    u_safe = u_vals[i] + frac * (u_vals[i + 1] - u_vals[i])
                    break
            if u_safe is None:
                u_safe = u_vals[-1] if r_vals[-1] <= 1 else u_vals[0]
            row[f"U_safe_{col}"] = round(float(u_safe), 3)
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Section B: per-U
# ---------------------------------------------------------------------------

def _percentile_band(g, col):
    return g[col].quantile(.10), g[col].median(), g[col].quantile(.90), g[col].quantile(.99)


def plot_vs_u(df: pd.DataFrame, col: str, ylabel: str, title: str,
              hline=None, hline_label=None):
    """p50 (line+marker) with a p10-p90 shaded stability band, plus a p99
    marker, vs U -- one panel per scale. `hline` draws a guarantee-hold
    reference (e.g. alpha=1, R/D=1)."""
    scales = sorted(df["scale"].unique(), key=lambda s: PERIOD_US[s])
    fig, axes = plt.subplots(1, len(scales), figsize=(6 * len(scales), 4.2), squeeze=False)
    for ax, scale in zip(axes[0], scales):
        g = df[df.scale == scale]
        us = sorted(g["U"].unique())
        p10s, p50s, p90s, p99s = [], [], [], []
        for u in us:
            lo, med, hi, p99 = _percentile_band(g[g.U == u], col)
            p10s.append(lo); p50s.append(med); p90s.append(hi); p99s.append(p99)
        c, m = style(0)
        ax.fill_between(us, p10s, p90s, color=c, alpha=0.15, label="p10-p90 band")
        ax.plot(us, p50s, color=c, marker=m, markersize=6, linewidth=2, label="p50")
        ax.plot(us, p99s, color=PALETTE[1], marker=MARKERS[1], markersize=5,
                 linewidth=1.5, linestyle="--", label="p99")
        if hline is not None:
            ax.axhline(hline, color="#7f7f7f", linewidth=1.5, linestyle=":",
                        label=hline_label or f"={hline}")
        ax.set_xlabel("U"); ax.set_ylabel(ylabel); ax.set_title(f"{title} -- {scale}")
        ax.grid(alpha=0.25); ax.legend(fontsize=9)
    fig.tight_layout()
    return fig


def miss_rate_vs_u(df: pd.DataFrame):
    scales = sorted(df["scale"].unique(), key=lambda s: PERIOD_US[s])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, scale in enumerate(scales):
        g = df[df.scale == scale]
        per_u = g.groupby("U")["deadline_miss"].mean().reset_index().sort_values("U")
        c, m = style(i)
        ax.plot(per_u["U"], per_u["deadline_miss"], color=c, marker=m,
                 markersize=6, linewidth=2, label=scale)
    ax.set_xlabel("U"); ax.set_ylabel("deadline miss rate"); ax.set_ylim(-0.02, 1.02)
    ax.set_title("Deadline miss rate vs U"); ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout()
    return fig


def rc_percentiles_vs_u(df: pd.DataFrame):
    """p50 and p99 of R and C together, vs U -- same unit (microseconds),
    so one y-axis, two colors for R/C and linestyle for p50/p99 (never a
    second y-axis for a second metric of the same unit)."""
    scales = sorted(df["scale"].unique(), key=lambda s: PERIOD_US[s])
    fig, axes = plt.subplots(1, len(scales), figsize=(6.5 * len(scales), 4.5), squeeze=False)
    for ax, scale in zip(axes[0], scales):
        g = df[df.scale == scale]
        us = sorted(g["U"].unique())
        r50, r99, c50, c99 = [], [], [], []
        for u in us:
            gu = g[g.U == u]
            r50.append(gu["R_wall_us"].median()); r99.append(gu["R_wall_us"].quantile(.99))
            c50.append(gu["C_cputime_us"].median()); c99.append(gu["C_cputime_us"].quantile(.99))
        ax.plot(us, r50, color=PALETTE[0], marker=MARKERS[0], label="R p50")
        ax.plot(us, r99, color=PALETTE[0], marker=MARKERS[0], linestyle="--", alpha=0.6, label="R p99")
        ax.plot(us, c50, color=PALETTE[1], marker=MARKERS[1], label="C p50")
        ax.plot(us, c99, color=PALETTE[1], marker=MARKERS[1], linestyle="--", alpha=0.6, label="C p99")
        ax.set_xlabel("U"); ax.set_ylabel("microseconds"); ax.set_title(f"R and C vs U -- {scale}")
        ax.grid(alpha=0.25); ax.legend(fontsize=9)
    fig.tight_layout()
    return fig
