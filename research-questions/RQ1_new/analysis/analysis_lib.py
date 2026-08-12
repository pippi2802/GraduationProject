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
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
CLEAN = HERE / "clean_data"
RESULTS = HERE.parent / "results"

# scale -> period (P), microseconds. Same values as every model's config.yaml.
PERIOD_US = {"tight": 10_000, "soft": 100_000}

# Matches a results/ round directory name, e.g. "model3-w2_sib_res_ptrchase_round4".
NAME_RE = re.compile(
    r"^(?P<model>model\d(?:-w\d)?)"
    r"(?:_(?P<arm>sib_cfs|sib_res|phys_cfs|phys_res))?"
    r"(?:_(?P<workload>ptrchase))?"
    r"_round(?P<round>\d+)$"
)

# Qualitative, colorblind-considered, high-contrast palette -- reused as-is
# from result.py (already validated there for this exact purpose: distinct
# hue AND marker per U series, order fixed/not cycled arbitrarily).
PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
           "#17becf", "#8c564b", "#e377c2", "#bcbd22", "#7f7f7f"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*", "<", ">"]


def style(i):
    return PALETTE[i % len(PALETTE)], MARKERS[i % len(MARKERS)]


def all_rounds(model: str, kind: str = "matmul") -> list[str]:
    """Every round directory in results/ matching this model+kind, found by
    globbing the directory name against NAME_RE -- NOT filtered by any
    per-round validity audit. As of 2026-08-10 this notebook pools
    everything collected for a model/kind, on the working assumption that a
    co-runner was actually running whenever placed there, rather than the
    round-by-round liveness audit build_clean_dataset.py/ROUND_STATUS used
    to apply (that module still exists and still works, just isn't the data
    source this notebook reads from anymore -- see the intro markdown)."""
    out = []
    for d in sorted(RESULTS.glob(f"{model}_*round*")):
        m = NAME_RE.match(d.name)
        if not m or m.group("model") != model:
            continue
        workload = m.group("workload") or "matmul"
        if workload != kind:
            continue
        out.append(d.name)
    return out


def load_model(model: str, kind: str = "matmul") -> pd.DataFrame:
    """Load clean_data/<model>.csv (curated, ROUND_STATUS-filtered, built by
    build_clean_dataset.py) and attach derived columns, filtered to one
    workload kind. REVERTED 2026-08-11 back to the curated source: the
    naive-joined approach (clean_data/<model>_<kind>_joined.csv, used
    2026-08-10 evening) pools every round found in results/ with no
    liveness/coin-flip exclusion, which reintroduces exactly the
    contamination the model3-w2 round-merge fix removed. Rerun
    build_clean_dataset.py after collecting/merging new rounds."""
    f = CLEAN / f"{model}.csv"
    if not f.exists():
        print(f"[analysis_lib] {model}: no clean_data/{model}.csv -- nothing valid pooled yet (check clean_data/MANIFEST.json)")
        return pd.DataFrame()
    df = pd.read_csv(f)
    if "kind" not in df.columns:
        return pd.DataFrame()
    df = df[df["kind"] == kind].reset_index(drop=True)
    df["P"] = df["scale"].map(PERIOD_US)
    df["Q"] = (df["U"] * df["P"]).round()
    df["bound"] = (2 * (df["P"] - df["Q"])).clip(lower=1)
    df["alpha"] = df["C_cputime_us"] / df["Q"]
    df["delta"] = (df["R_wall_us"] - df["C_cputime_us"]) / df["bound"]
    df["RoverD"] = df["R_wall_us"] / df["P"]
    df["added_latency_us"] = df["R_wall_us"] - df["C_cputime_us"]  # raw delta
    # ms counterparts -- display unit for every raw-time plot/table below
    # (alpha/delta/RoverD stay unitless ratios, untouched). Source data and
    # config.yaml periods stay in microseconds; only presentation changes.
    df["R_wall_ms"] = df["R_wall_us"] / 1000
    df["C_cputime_ms"] = df["C_cputime_us"] / 1000
    df["added_latency_ms"] = df["added_latency_us"] / 1000
    return df


def load_model_both(model: str) -> pd.DataFrame:
    """Both kinds concatenated, `kind` column intact -- used only by Section
    C's direct matmul-vs-ptrchase comparison."""
    frames = [load_model(model, k) for k in ("matmul", "ptrchase")]
    frames = [d for d in frames if not d.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Section A: pooled-dataset-level
# ---------------------------------------------------------------------------

def descriptives_table(df: pd.DataFrame) -> pd.DataFrame:
    """Basic descriptives for R and C (ms), per scale. A table, not a plot --
    exact numbers are more useful here than a picture."""
    rows = []
    for scale, g in df.groupby("scale"):
        for col, label in [("R_wall_ms", "R (response, ms)"), ("C_cputime_ms", "C (execution, ms)")]:
            s = g[col]
            rows.append({
                "scale": scale, "metric": label, "n": len(s),
                "mean": round(s.mean(), 3), "std": round(s.std(), 3),
                "min": round(s.min(), 3), "p50": round(s.median(), 3),
                "p95": round(s.quantile(.95), 3), "p99": round(s.quantile(.99), 3),
                "p999": round(s.quantile(.999), 3), "max": round(s.max(), 3),
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


def round_stability_table(model: str, kind: str = "matmul") -> pd.DataFrame:
    """Per-round miss_rate/C_p50 side by side, straight from EVERY round
    found in results/ for this model+kind (via all_rounds -- no per-round
    exclusion applied, see load_model). Still worth keeping as a standing
    QA check even without the audit: a round whose numbers don't match its
    siblings at the same U is exactly the coin-flip tell, and this is the
    only place that's visible (the pooled CSV alone hides it)."""
    import build_clean_dataset as bcd
    included = all_rounds(model, kind)
    frames = []
    for r in included:
        d = bcd.load_round(model, r)
        if d.empty:
            continue
        d = d[d["kind"] == kind]
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


def longest_miss_run_table(model: str, kind: str = "matmul") -> pd.DataFrame:
    """Longest run of CONSECUTIVE missed deadlines, per scale/U -- a
    temporal statistic, so (per result.py's pool() docstring) computed
    per-round on that round's own job_index-ordered sequence, then MAXED
    across every round found (all_rounds -- no per-round exclusion, see
    load_model) -- never concatenate raw sequences across rounds for this
    one, that would fabricate a run spanning a boundary between two
    unrelated collection times that never actually happened."""
    import build_clean_dataset as bcd
    included = all_rounds(model, kind)
    best = {}
    for r in included:
        d = bcd.load_round(model, r)
        if d.empty:
            continue
        d = d[d["kind"] == kind]
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


def data_quality_table(model: str, kind: str = "matmul", expected_n: int = 5000) -> pd.DataFrame:
    """Per round found (all_rounds -- no per-round exclusion, see
    load_model): row-count / dtype / physical-sanity checks straight from
    that round's raw jobs.csv (not the pooled file, same reasoning as
    round_stability_table -- pooling would hide which specific round+cell a
    problem came from). Flags, per cell: n != expected_n, duplicate
    job_index, NaN in R/C/deadline_miss, C<=0, or R < C (physically
    impossible -- wall response time can't be shorter than the execution
    time it contains, a sign of a corrupted/misaligned row).

    Note this only catches CORRUPTED rows, not the liveness/coin-flip issue
    (a co-runner that's Ready but not actually consuming CPU) -- that
    produces perfectly well-formed rows with an understated C, invisible to
    these checks. As of 2026-08-10 this notebook doesn't re-verify that
    per round; see the intro markdown for why."""
    import build_clean_dataset as bcd
    included = all_rounds(model, kind)
    out = []
    for r in included:
        d = bcd.load_round(model, r)
        if d.empty:
            out.append({"round": r, "cells": 0, "bad_cells": 0, "issues": "no data found"})
            continue
        d = d[d["kind"] == kind]
        if d.empty:
            continue
        n_cells = 0
        bad_cells = 0
        issues = []
        for (scale, u), g in d.groupby(["scale", "U"]):
            n_cells += 1
            cell_issues = []
            if len(g) != expected_n:
                cell_issues.append(f"n={len(g)} (expected {expected_n})")
            if g["job_index"].duplicated().any():
                cell_issues.append("duplicate job_index")
            for col in ["R_wall_us", "C_cputime_us", "deadline_miss"]:
                if g[col].isna().any():
                    cell_issues.append(f"NaN in {col}")
            n_r_lt_c = int((g["R_wall_us"] < g["C_cputime_us"]).sum())
            if n_r_lt_c:
                cell_issues.append(f"R<C in {n_r_lt_c} job(s)")
            if (g["C_cputime_us"] <= 0).any():
                cell_issues.append("C<=0 present")
            if cell_issues:
                bad_cells += 1
                issues.append(f"{scale}/U{u}: " + "; ".join(cell_issues))
        out.append({"round": r, "cells": n_cells, "bad_cells": bad_cells,
                     "issues": " | ".join(issues) if issues else ""})
    return pd.DataFrame(out)


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
    """p50 and p99 of R and C together, vs U -- same unit (milliseconds),
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
            r50.append(gu["R_wall_ms"].median()); r99.append(gu["R_wall_ms"].quantile(.99))
            c50.append(gu["C_cputime_ms"].median()); c99.append(gu["C_cputime_ms"].quantile(.99))
        ax.plot(us, r50, color=PALETTE[0], marker=MARKERS[0], label="R p50")
        ax.plot(us, r99, color=PALETTE[0], marker=MARKERS[0], linestyle="--", alpha=0.6, label="R p99")
        ax.plot(us, c50, color=PALETTE[1], marker=MARKERS[1], label="C p50")
        ax.plot(us, c99, color=PALETTE[1], marker=MARKERS[1], linestyle="--", alpha=0.6, label="C p99")
        ax.set_xlabel("U"); ax.set_ylabel("milliseconds"); ax.set_title(f"R and C vs U -- {scale}")
        ax.grid(alpha=0.25); ax.legend(fontsize=9)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Section C: matmul vs ptrchase (workload / "kind") comparison
# ---------------------------------------------------------------------------

def kind_comparison_table(df: pd.DataFrame) -> pd.DataFrame:
    """Side-by-side matmul vs ptrchase, per scale/U, for a model whose
    pooled data contains both kinds (load_model called without a `kind`
    filter). Includes the C_p50 ratio ptrchase/matmul -- the headline number
    for "is this arm's contention mechanism more or less felt by a
    memory-latency-bound workload than a compute-bound one"."""
    rows = []
    for (scale, u, kind), g in df.groupby(["scale", "U", "kind"]):
        rows.append({
            "scale": scale, "U": u, "kind": kind, "n": len(g),
            "miss_rate": round(g["deadline_miss"].mean(), 4),
            "C_p50_ms": round(g["C_cputime_ms"].median(), 3),
        })
    long = pd.DataFrame(rows)
    if long.empty:
        return long
    piv = long.pivot_table(index=["scale", "U"], columns="kind", values=["miss_rate", "C_p50_ms"])
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    if "C_p50_ms_matmul" in piv.columns and "C_p50_ms_ptrchase" in piv.columns:
        piv["C_p50_ratio_ptrchase_over_matmul"] = (piv["C_p50_ms_ptrchase"] / piv["C_p50_ms_matmul"]).round(3)
    return piv.reset_index().sort_values(["scale", "U"])


def plot_kind_comparison(df: pd.DataFrame, col: str, ylabel: str, title: str):
    """p50 of `col` vs U, one line per kind (matmul/ptrchase), one panel per
    scale -- direct visual comparison, not a stability band (that's what
    plot_vs_u is for on a single kind); the point here is the GAP between
    the two lines, not the spread within one."""
    scales = sorted(df["scale"].unique(), key=lambda s: PERIOD_US[s])
    kinds = sorted(df["kind"].unique())
    fig, axes = plt.subplots(1, len(scales), figsize=(6 * len(scales), 4.2), squeeze=False)
    for ax, scale in zip(axes[0], scales):
        g = df[df.scale == scale]
        for i, kind in enumerate(kinds):
            gk = g[g.kind == kind]
            us = sorted(gk["U"].unique())
            p50s = [gk[gk.U == u][col].median() for u in us]
            c, m = style(i)
            ax.plot(us, p50s, color=c, marker=m, markersize=6, linewidth=2, label=kind)
        ax.set_xlabel("U"); ax.set_ylabel(ylabel); ax.set_title(f"{title} -- {scale}")
        ax.grid(alpha=0.25); ax.legend(fontsize=9)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Section D: one table/figure per thesis claim
# ---------------------------------------------------------------------------

def noise_floor_table(df: pd.DataFrame) -> pd.DataFrame:
    """Coefficient of variation (std/mean) of C and R per scale/U -- Claim 0's
    evidence. Small and roughly flat across U is the signature of
    irreducible IaaS/hypervisor noise, as opposed to a real contention
    effect (which shows elevated tails and a threshold-crossing miss rate,
    not just a slightly wider spread around the same median)."""
    rows = []
    for (scale, u), g in df.groupby(["scale", "U"]):
        for col, label in [("C_cputime_ms", "C"), ("R_wall_ms", "R")]:
            s = g[col]
            rows.append({
                "scale": scale, "U": u, "metric": label,
                "mean_ms": round(s.mean(), 3), "std_ms": round(s.std(), 3),
                "cv": round(s.std() / s.mean(), 4) if s.mean() else None,
            })
    return pd.DataFrame(rows).sort_values(["scale", "U", "metric"])


def arm_comparison_table(models: list, kind: str = "matmul") -> pd.DataFrame:
    """Miss rate and alpha side by side across several models/arms, same
    workload kind -- Claim 2's evidence for the physical-vs-sibling,
    reserved-vs-unreserved decomposition. One row per (scale,U), one
    miss/alpha column pair per arm."""
    frames = []
    for m in models:
        df = load_model(m, kind=kind)
        if df.empty:
            continue
        g = df.groupby(["scale", "U"]).agg(miss=("deadline_miss", "mean"), Cp50=("C_cputime_us", "median")).reset_index()
        g["Q"] = (g["U"] * g["scale"].map(PERIOD_US)).round()
        g["alpha"] = (g["Cp50"] / g["Q"]).round(3)
        g["arm"] = m
        frames.append(g[["scale", "U", "arm", "miss", "alpha"]])
    if not frames:
        return pd.DataFrame()
    long = pd.concat(frames, ignore_index=True)
    piv = long.pivot_table(index=["scale", "U"], columns="arm", values=["miss", "alpha"])
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    return piv.reset_index().sort_values(["scale", "U"])


def plot_arm_comparison(models: list, kind: str, col: str, ylabel: str, title: str):
    """One line per arm/model vs U, one panel per scale -- Claim 2's figure:
    physical arms should sit flat/low throughout, sibling arms should show
    real movement, distinguishing "shares a physical core" from "another
    workload merely exists on the node"."""
    frames = {}
    for m in models:
        df = load_model(m, kind=kind)
        if not df.empty:
            frames[m] = df
    if not frames:
        return None
    scales = sorted(set().union(*[set(d["scale"].unique()) for d in frames.values()]), key=lambda s: PERIOD_US[s])
    fig, axes = plt.subplots(1, len(scales), figsize=(6.5 * len(scales), 4.5), squeeze=False)
    for ax, scale in zip(axes[0], scales):
        for i, (m, d) in enumerate(frames.items()):
            g = d[d.scale == scale]
            if g.empty:
                continue
            us = sorted(g["U"].unique())
            vals = [g[g.U == u][col].mean() for u in us]
            c, mk = style(i)
            ax.plot(us, vals, color=c, marker=mk, markersize=6, linewidth=2, label=m)
        ax.set_xlabel("U"); ax.set_ylabel(ylabel); ax.set_title(f"{title} -- {scale}")
        ax.grid(alpha=0.25); ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def severity_table(model: str, kind: str = "matmul") -> pd.DataFrame:
    """Miss rate, alpha, and longest consecutive miss run together --
    Claim 3's evidence that misses cluster exactly where alpha crosses 1
    (a throttling cliff), not scattered randomly across U."""
    df = load_model(model, kind=kind)
    if df.empty:
        return df
    g = df.groupby(["scale", "U"]).agg(n=("deadline_miss", "size"), miss=("deadline_miss", "mean"), Cp50=("C_cputime_us", "median")).reset_index()
    g["Q"] = (g["U"] * g["scale"].map(PERIOD_US)).round()
    g["alpha"] = (g["Cp50"] / g["Q"]).round(3)
    burst = longest_miss_run_table(model, kind=kind)
    if burst.empty:
        g["longest_consecutive_miss_run"] = None
        return g[["scale", "U", "n", "miss", "alpha", "longest_consecutive_miss_run"]]
    merged = g.merge(burst, on=["scale", "U"], how="left")
    return merged[["scale", "U", "n", "miss", "alpha", "longest_consecutive_miss_run"]]


def plot_noise_floor(df: pd.DataFrame, metric: str = "C"):
    """Coefficient of variation vs U, one line per scale -- Claim 0's
    figure. Flat and small across the whole sweep is the noise-floor
    signature; a rising or spiking line would instead look like a real
    effect creeping in."""
    t = noise_floor_table(df)
    t = t[t["metric"] == metric]
    scales = sorted(t["scale"].unique(), key=lambda s: PERIOD_US[s])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, scale in enumerate(scales):
        g = t[t.scale == scale].sort_values("U")
        c, m = style(i)
        ax.plot(g["U"], g["cv"], color=c, marker=m, markersize=6, linewidth=2, label=scale)
    ax.set_xlabel("U"); ax.set_ylabel(f"coefficient of variation ({metric})")
    ax.set_title(f"Claim 0: noise floor, {metric}, model1 solo baseline")
    ax.grid(alpha=0.25); ax.legend()
    fig.tight_layout()
    return fig


def plot_round_stability(model: str, kind: str = "matmul"):
    """Miss rate vs U, one line per round -- Claim 1's figure. A round that
    stands apart from the others (rather than every round tracking closely)
    is the visual signature of a per-round admission failure, not a smooth
    per-U effect."""
    t = round_stability_table(model, kind=kind)
    if t.empty:
        return None
    miss_cols = [c for c in t.columns if not str(c).startswith("C_p50")]
    t = t[miss_cols].reset_index()
    scales = sorted(t["scale"].unique(), key=lambda s: PERIOD_US[s])
    fig, axes = plt.subplots(1, len(scales), figsize=(7 * len(scales), 4.5), squeeze=False)
    for ax, scale in zip(axes[0], scales):
        g = t[t.scale == scale].sort_values("U")
        for i, col in enumerate([c for c in miss_cols if c not in ("scale", "U")]):
            c, m = style(i)
            ax.plot(g["U"], g[col], color=c, marker=m, markersize=6, linewidth=2, label=col)
        ax.set_xlabel("U"); ax.set_ylabel("deadline miss rate"); ax.set_ylim(-0.02, 1.02)
        ax.set_title(f"Claim 1: {model} ({kind}) per-round miss rate -- {scale}")
        ax.grid(alpha=0.25); ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def plot_severity(model: str, kind: str = "matmul"):
    """Miss rate and longest-consecutive-miss-run vs U side by side, same
    x-axis -- Claim 3's figure. The two lines rising and falling together
    is the visual case that misses are concentrated bursts tied to the same
    utilization levels, not scattered independent events."""
    t = severity_table(model, kind=kind)
    if t.empty:
        return None
    scales = sorted(t["scale"].unique(), key=lambda s: PERIOD_US[s])
    fig, axes = plt.subplots(len(scales), 2, figsize=(12, 4.2 * len(scales)), squeeze=False)
    for row, scale in enumerate(scales):
        g = t[t.scale == scale].sort_values("U")
        ax1, ax2 = axes[row]
        ax1.plot(g["U"], g["miss"], color=PALETTE[0], marker=MARKERS[0], markersize=6, linewidth=2)
        ax1.set_xlabel("U"); ax1.set_ylabel("deadline miss rate"); ax1.set_ylim(-0.02, 1.02)
        ax1.set_title(f"miss rate -- {scale}"); ax1.grid(alpha=0.25)
        ax2.plot(g["U"], g["longest_consecutive_miss_run"], color=PALETTE[1], marker=MARKERS[1], markersize=6, linewidth=2)
        ax2.set_xlabel("U"); ax2.set_ylabel("longest consecutive miss run (jobs)")
        ax2.set_title(f"longest miss burst -- {scale}"); ax2.grid(alpha=0.25)
    fig.suptitle(f"Claim 3: {model} ({kind}), miss rate vs. burst length")
    fig.tight_layout()
    return fig


def plot_safe_margin(models: list, kind: str, percentile: float = 0.99):
    """p99 (or p999) of R/D vs U, one line per arm, one panel per scale, with
    a reference line at 1 -- Claim 4's figure. Where a line crosses the
    reference line is exactly the U_safe number in the table; seeing it as
    a crossing point makes the threshold concrete instead of an abstract
    single number."""
    frames = {}
    for m in models:
        df = load_model(m, kind=kind)
        if not df.empty:
            frames[m] = df
    if not frames:
        return None
    scales = sorted(set().union(*[set(d["scale"].unique()) for d in frames.values()]), key=lambda s: PERIOD_US[s])
    fig, axes = plt.subplots(1, len(scales), figsize=(7 * len(scales), 4.5), squeeze=False)
    for ax, scale in zip(axes[0], scales):
        for i, (m, d) in enumerate(frames.items()):
            g = d[d.scale == scale]
            if g.empty:
                continue
            us = sorted(g["U"].unique())
            vals = [g[g.U == u]["RoverD"].quantile(percentile) for u in us]
            c, mk = style(i)
            ax.plot(us, vals, color=c, marker=mk, markersize=6, linewidth=2, label=m)
        ax.axhline(1, color="#7f7f7f", linewidth=1.5, linestyle=":", label="R/D = 1 (deadline)")
        ax.set_xlabel("U"); ax.set_ylabel(f"R/D, p{int(percentile*100)}")
        ax.set_title(f"Claim 4: safe margin ({kind}) -- {scale}")
        ax.grid(alpha=0.25); ax.legend(fontsize=8)
    fig.tight_layout()
    return fig
