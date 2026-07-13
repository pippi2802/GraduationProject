#!/usr/bin/env python3
"""
join_covariates.py — thin CLI over the SHARED joiner (common/rtmetrics/covariates).

Model 2's per-cell join (per-task / per-reservation) now lives in
common/rtmetrics/covariates.join_percell; this wrapper just exposes it on the
command line for manual use. analyze.py calls the shared function directly.

Usage:
  join_covariates.py --cell-dir results/<tb>/intra/<scale>/<cell-id> \
                     --samples-dir results/<tb>/samples
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # model2/parse
sys.path.insert(0, str(HERE.parent.parent / "common"))  # RQ1/common
from rtmetrics import covariates  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="per-cell covariate join (Model 2)")
    ap.add_argument("--cell-dir", required=True)
    ap.add_argument("--samples-dir", required=True)
    args = ap.parse_args()
    n = covariates.join_percell(Path(args.cell_dir), Path(args.samples_dir))
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
