#!/usr/bin/env python3
"""
rtmetrics.plotting — shared plotting primitives for the RQ1 models (clean,
linear-axis, slide-friendly). Figure SETS stay per-model (each model plots
different things); only the reusable style/readers/helpers live here.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SCALE_COLOR = {"tight": "#c1121f", "soft": "#1d4e89"}
SCALE_LABEL = {"tight": "tight (P=10 ms)", "soft": "soft (P=100 ms)"}


def apply_style():
    plt.rcParams.update({
        "figure.figsize": (8, 5), "figure.dpi": 120, "savefig.dpi": 150,
        "font.size": 12, "axes.grid": True, "grid.alpha": 0.3,
        "axes.spines.top": False, "axes.spines.right": False,
        "lines.linewidth": 2, "lines.markersize": 6,
    })


def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path) as fh:
        return list(csv.DictReader(fh))


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def by_scale(rows):
    out = {}
    for r in rows:
        out.setdefault(r["scale"], []).append(r)
    for s in out:
        out[s].sort(key=lambda x: fnum(x.get("U")) or 0)
    return out


def jobcol(cell_dir, fname, col, cov=False):
    """Read one numeric column from a per-job CSV (optionally *_with_covariates)."""
    stem = Path(fname).stem
    name = f"{stem}_with_covariates.csv" if cov else fname
    p = Path(cell_dir) / name
    out = []
    if not p.exists():
        return out
    with open(p) as fh:
        header = None
        for r in csv.reader(fh):
            if not r or r[0].startswith("#"):
                continue
            if header is None:
                header = r; idx = {x: i for i, x in enumerate(header)}; continue
            try:
                out.append(float(r[idx[col]]))
            except (ValueError, KeyError):
                out.append(None)
    return out


def ccdf(ax, values, **kw):
    """Plot a complementary CDF of values (ms on x) on the given axis."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return
    n = len(vals)
    yc = [1 - (i + 1) / n for i in range(n)]
    ax.plot([v / 1000 for v in vals], yc, **kw)


def save(fig, outdir, name, formats=("png", "pdf")):
    """Save a figure. If `name` already ends in .png/.pdf/.svg write exactly that
    (single file); otherwise write one file per `formats` extension."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem, ext = os.path.splitext(name)
    if ext.lower() in (".png", ".pdf", ".svg"):
        p = outdir / name
        fig.savefig(p, bbox_inches="tight")
        plt.close(fig)
        print(f"[plot] {p}")
        return
    for f in formats:
        fig.savefig(outdir / f"{name}.{f}", bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] {outdir / name}.{formats[0]}" + (" (+pdf)" if "pdf" in formats else ""))
