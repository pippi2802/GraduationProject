#!/usr/bin/env python3
"""
join_covariates.py — thin CLI over the SHARED joiner
(common/rtmetrics/covariates.join_model1_1). Model 1_1's single-reservation join
(jobs.csv -> jobs_with_covariates.csv) now lives in the shared library; this
wrapper exposes it on the command line (analyze.py invokes it per cell).

Usage:
  join_covariates.py --cell-dir results/<tb>/<scale>/U<u> --samples-dir results/<tb>/samples
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))  # RQ1/common
from rtmetrics import covariates  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="join per-job rows to covariates (Model 1_1)")
    ap.add_argument("--cell-dir", required=True)
    ap.add_argument("--samples-dir", required=True)
    args = ap.parse_args()
    n = covariates.join_model1_1(Path(args.cell_dir), Path(args.samples_dir))
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
