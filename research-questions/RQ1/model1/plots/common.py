#!/usr/bin/env python3
"""
plots/common.py — shared helpers for the Model 1 figure scripts.

One place for: config + results discovery, per-cell CSV loading (jobs / server /
covariates + cell.json), aggregation ACROSS time-blocks, percentile helpers, a
consistent matplotlib style, and the figures output directory.

Every figure script imports from here so loading/styling stays DRY and every
figure is regenerable from results/ alone.

CSV schemas (produced by parse/ and sampler/):
  jobs.csv        job_index,release_us,start_us,finish_us,C_us,R_us,slack_us,
                  deadline_miss,tardiness_us
  server.csv      ts_raw_ns,ts_wall_ns,target,pid,cpu,usage_usec,user_usec,
                  system_usec,nr_periods,nr_throttled,throttled_usec
  covariates.csv  ts_raw_ns,ts_wall_ns,target,pid,tid,cpu,steal_jiffies,
                  irq_jiffies,softirq_jiffies,sched_runtime_ns,sched_rundelay_ns,
                  sched_timeslices,interrupts_cum,softirqs_cum,gap_flag
  cell.json       cell metadata (P_us, Q_us, U, scale, reservation, cpu_used, ...)

Results layout: results/<timeblock>/<scale-dir>/U<U>/<file>
                figures land in results/<timeblock or 'aggregate'>/figures/
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")           # headless: save files, never open a window
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import model1lib as m1  # noqa: E402

SCALE_ORDER = ["tight", "soft"]
SCALE_LABEL = {"tight": "tight (P = 10 ms)", "soft": "soft (P = 100 ms)"}
PCTLS = [50, 99, 99.9]          # headline percentiles (max handled separately)
RESERVED_DIRNAMES = {"figures", "aggregate"}

# CLK_TCK: /proc jiffies -> seconds. On the sampler host this is os.sysconf, but
# figures may render on a different machine; 100 Hz is the Linux default.
try:
    CLK_TCK = os.sysconf("SC_CLK_TCK")
except (ValueError, OSError, AttributeError):
    CLK_TCK = 100


# --------------------------------------------------------------------------- #
# config / discovery
# --------------------------------------------------------------------------- #
def load_config():
    return m1.load_config()


def results_root(cfg=None) -> Path:
    cfg = cfg or load_config()
    return ROOT / cfg["results"]["root"]


def scale_dir_map(cfg) -> dict:
    """scale-dir name -> scale key, e.g. 'tight-10ms' -> 'tight'."""
    return {sc["dir"]: name for name, sc in cfg["scales"].items()}


def u_from_dirname(name: str):
    """'U0.95' -> 0.95 ; returns None if not a U dir."""
    if not name.startswith("U"):
        return None
    try:
        return float(name[1:])
    except ValueError:
        return None


def list_timeblocks(cfg=None) -> list[str]:
    root = results_root(cfg)
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir()
                  if d.is_dir() and d.name not in RESERVED_DIRNAMES)


def discover_cells(timeblock: str = "aggregate", cfg=None) -> dict:
    """Return {(scale, u): [cell_dir, ...]} for a time-block, or ALL blocks
    combined when timeblock == 'aggregate'. Cell dirs are the leaf U<U>/ dirs."""
    cfg = cfg or load_config()
    root = results_root(cfg)
    dmap = scale_dir_map(cfg)
    blocks = list_timeblocks(cfg) if timeblock == "aggregate" else [timeblock]
    cells: dict = {}
    for tb in blocks:
        tb_dir = root / tb
        if not tb_dir.is_dir():
            continue
        for sdir in tb_dir.iterdir():
            scale = dmap.get(sdir.name)
            if scale is None or not sdir.is_dir():
                continue
            for udir in sdir.iterdir():
                u = u_from_dirname(udir.name)
                if u is None or not udir.is_dir():
                    continue
                cells.setdefault((scale, u), []).append(udir)
    return cells


def sorted_cell_keys(cells: dict, scale: str) -> list:
    return sorted((k for k in cells if k[0] == scale), key=lambda k: k[1])


def figures_dir(timeblock: str = "aggregate", cfg=None) -> Path:
    cfg = cfg or load_config()
    d = results_root(cfg) / timeblock / "figures"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --------------------------------------------------------------------------- #
# loaders
# --------------------------------------------------------------------------- #
def _read_csv_dicts(path: Path):
    with open(path, newline="", encoding="utf-8") as fh:
        yield from csv.DictReader(fh)


def _to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def load_jobs(cell_dirs, cfg=None) -> dict:
    """Aggregate per-job arrays across the given cell dirs (across time-blocks).

    Returns dict of numpy arrays: R_us, C_us, slack_us, tardiness_us, miss,
    release_us (per-block-relative), block (index), plus a per-block list for
    time-block comparison plots.
    """
    cfg = cfg or load_config()
    fname = cfg["results"]["per_job_csv"]
    R, C, S, T, M, rel, blk, blocks = [], [], [], [], [], [], [], []
    for bi, d in enumerate(cell_dirs):
        p = Path(d) / fname
        if not p.exists():
            continue
        r0 = None
        rr = []
        for row in _read_csv_dicts(p):
            rv = _to_float(row.get("R_us"))
            if np.isnan(rv):
                continue
            R.append(rv)
            C.append(_to_float(row.get("C_us")))
            S.append(_to_float(row.get("slack_us")))
            T.append(_to_float(row.get("tardiness_us")))
            M.append(1 if str(row.get("deadline_miss")).strip() in ("1", "1.0") else 0)
            relu = _to_float(row.get("release_us"))
            if r0 is None and not np.isnan(relu):
                r0 = relu
            rel.append((relu - r0) if (r0 is not None and not np.isnan(relu)) else np.nan)
            blk.append(bi)
            rr.append(rv)
        if rr:
            blocks.append({"dir": Path(d), "R_us": np.asarray(rr)})
    return {
        "R_us": np.asarray(R), "C_us": np.asarray(C), "slack_us": np.asarray(S),
        "tardiness_us": np.asarray(T), "miss": np.asarray(M),
        "release_us": np.asarray(rel), "block": np.asarray(blk),
        "blocks": blocks,
    }


def load_covariates(cell_dirs, cfg=None, target="rt") -> dict:
    """Concatenate covariate samples (one target) across blocks, per-block
    relative elapsed time (raw-monotonic). Cumulative counters are returned as-is;
    use cumulative_rate_per_window() to diff them.
    """
    cfg = cfg or load_config()
    fname = cfg["results"]["covariates_csv"]
    out = {"elapsed_us": [], "steal_j": [], "irq_j": [], "softirq_j": [],
           "rundelay_ns": [], "irq_cum": [], "softirq_cum": [], "gap": [], "block": []}
    for bi, d in enumerate(cell_dirs):
        p = Path(d) / fname
        if not p.exists():
            continue
        t0 = None
        for row in _read_csv_dicts(p):
            if row.get("target") != target:
                continue
            traw = _to_float(row.get("ts_raw_ns"))
            if np.isnan(traw):
                continue
            if t0 is None:
                t0 = traw
            out["elapsed_us"].append((traw - t0) / 1000.0)
            out["steal_j"].append(_to_float(row.get("steal_jiffies")))
            out["irq_j"].append(_to_float(row.get("irq_jiffies")))
            out["softirq_j"].append(_to_float(row.get("softirq_jiffies")))
            out["rundelay_ns"].append(_to_float(row.get("sched_rundelay_ns")))
            out["irq_cum"].append(_to_float(row.get("interrupts_cum")))
            out["softirq_cum"].append(_to_float(row.get("softirqs_cum")))
            out["gap"].append(_to_float(row.get("gap_flag")))
            out["block"].append(bi)
    return {k: np.asarray(v) for k, v in out.items()}


def load_meta(cell_dirs, cfg=None) -> dict | None:
    """First available cell.json among the dirs (they share P/Q/U)."""
    cfg = cfg or load_config()
    fname = cfg["results"]["cell_metadata_json"]
    for d in cell_dirs:
        p = Path(d) / fname
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
    return None


# --------------------------------------------------------------------------- #
# stats helpers
# --------------------------------------------------------------------------- #
def pct(a, q):
    a = np.asarray(a, dtype=float)
    a = a[~np.isnan(a)]
    return float(np.percentile(a, q)) if a.size else np.nan


def summary_percentiles(a, qs=PCTLS):
    return {q: pct(a, q) for q in qs}


def ccdf(a):
    """Return (sorted_values, survival) for a log-tail CCDF plot."""
    a = np.sort(np.asarray(a, dtype=float))
    a = a[~np.isnan(a)]
    n = a.size
    if n == 0:
        return np.array([]), np.array([])
    surv = 1.0 - (np.arange(1, n + 1) / n)
    return a, surv


def ecdf(a):
    a = np.sort(np.asarray(a, dtype=float))
    a = a[~np.isnan(a)]
    n = a.size
    if n == 0:
        return np.array([]), np.array([])
    return a, np.arange(1, n + 1) / n


def rule_of_three_upper(n: int) -> float:
    """Upper 95% bound on a rate when 0 events are observed in n trials (3/n)."""
    return 3.0 / n if n > 0 else np.nan


def window_reduce(elapsed_us, values, window_s: float, reducer):
    """Bin (elapsed_us, values) into fixed windows; apply reducer per window.
    Returns (window_center_s, reduced). NaNs ignored."""
    elapsed_us = np.asarray(elapsed_us, dtype=float)
    values = np.asarray(values, dtype=float)
    ok = ~np.isnan(elapsed_us) & ~np.isnan(values)
    elapsed_us, values = elapsed_us[ok], values[ok]
    if elapsed_us.size == 0:
        return np.array([]), np.array([])
    w_us = window_s * 1e6
    idx = (elapsed_us // w_us).astype(int)
    centers, reduced = [], []
    for b in np.unique(idx):
        sel = idx == b
        centers.append((b + 0.5) * window_s)
        reduced.append(reducer(values[sel]))
    return np.asarray(centers), np.asarray(reduced)


def cumulative_rate_per_window(elapsed_us, cum_counter, window_s: float):
    """Delta of a cumulative counter per fixed time window -> (center_s, delta)."""
    elapsed_us = np.asarray(elapsed_us, dtype=float)
    cum = np.asarray(cum_counter, dtype=float)
    ok = ~np.isnan(elapsed_us) & ~np.isnan(cum)
    elapsed_us, cum = elapsed_us[ok], cum[ok]
    if elapsed_us.size < 2:
        return np.array([]), np.array([])
    w_us = window_s * 1e6
    idx = (elapsed_us // w_us).astype(int)
    centers, deltas = [], []
    for b in np.unique(idx):
        sel = idx == b
        c = cum[sel]
        centers.append((b + 0.5) * window_s)
        deltas.append(float(c.max() - c.min()))
    return np.asarray(centers), np.asarray(deltas)


# --------------------------------------------------------------------------- #
# styling / saving
# --------------------------------------------------------------------------- #
def set_style():
    plt.rcParams.update({
        "figure.dpi": 120,
        "savefig.dpi": 200,
        "font.size": 10,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "lines.linewidth": 1.6,
    })


def u_colors(us):
    cmap = plt.get_cmap("viridis")
    us = list(us)
    return {u: cmap(i / max(1, len(us) - 1)) for i, u in enumerate(us)}


def save(fig, outdir: Path, stem: str):
    outdir.mkdir(parents=True, exist_ok=True)
    png, pdf = outdir / f"{stem}.png", outdir / f"{stem}.pdf"
    fig.savefig(png, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    sys.stderr.write(f"wrote {png}\n")
    return png


def add_timeblock_arg(ap):
    ap.add_argument("--timeblock", default="aggregate",
                    help="time-block label, or 'aggregate' (default) to combine all")
    ap.add_argument("--config", default=None)
    return ap


def require_cells(cells: dict, name: str) -> bool:
    if not cells:
        sys.stderr.write(
            f"[{name}] no cells found under results/. Run a time-block first "
            f"(python run_model1.py --timeblock LABEL), then regenerate figures.\n")
        return False
    return True
