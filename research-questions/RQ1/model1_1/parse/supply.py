#!/usr/bin/env python3
"""
parse/supply.py — thin shim over the SHARED supply computation
(common/rtmetrics/metrics.supply_from_server) so Model 1_1's analyze.py keeps
`import supply as supplymod; supplymod.compute(cell_dir, samples_dir)`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))  # RQ1/common
from rtmetrics.metrics import supply_from_server as compute  # noqa: F401,E402
