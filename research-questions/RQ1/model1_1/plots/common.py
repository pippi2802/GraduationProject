#!/usr/bin/env python3
"""
plots/common.py — thin shim re-exporting the SHARED plotting helpers
(common/rtmetrics/plotting) so Model 1_1's plot_all.py keeps `import common as C`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))  # RQ1/common
from rtmetrics.plotting import (  # noqa: F401,E402
    SCALE_COLOR, SCALE_LABEL, apply_style, read_csv, fnum, by_scale, jobcol, ccdf, save,
)
