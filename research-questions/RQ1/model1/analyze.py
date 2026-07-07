#!/usr/bin/env python3
"""
analyze.py - OFFLINE post-processing for a Model 1 timeblock.

The sweep (run_model1.py) now only ACQUIRES raw data, keeping derived work OFF
the critical path so cells save fast:
  - per cell:  rt-app.log (raw) + jobs.csv (cheap parse) + cell.json (with the
               cell's [start_wall_ns, end_wall_ns] wall-clock window)
  - once at the end of the sweep: the FULL continuous sampler stream, copied to
               results/<timeblock>/samples/{server.csv, covariates.csv}

This script does the deferred/heavy part afterwards, at your convenience:
  - slices each cell's covariate window out of the shared sampler stream
  - (re)generates jobs.csv from rt-app.log if it is missing

Usage (run AFTER the sweep, on any machine that has the results/ tree):
    python3 analyze.py --timeblock tb-YYYYMMDD-HHMM

Then render figures separately with:
    python3 plots/plot_all.py --timeblock tb-YYYYMMDD-HHMM
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def slice_cell(samples_dir: Path, cell_dir: Path, start_ns: int, end_ns: int) -> None:
    """Cut this cell's covariate/server rows out of the shared sampler stream."""
    subprocess.run(
        [sys.executable, str(HERE / "parse" / "slice_covariates.py"),
         "--samples-dir", str(samples_dir), "--out-dir", str(cell_dir),
         "--start-wall-ns", str(start_ns), "--end-wall-ns", str(end_ns)],
        check=False,
    )


def ensure_jobs_csv(cell_dir: Path) -> None:
    """Regenerate jobs.csv from rt-app.log if it is absent (raw log is the source)."""
    jobs = cell_dir / "jobs.csv"
    log = cell_dir / "rt-app.log"
    if jobs.exists() or not log.exists():
        return
    sys.path.insert(0, str(HERE / "parse"))
    import parse_rtapp  # noqa: E402
    import csv as _csv
    # warm-up already discarded upstream in the live run; re-parse with 0 here so
    # analyze does not double-discard. jobs.csv from the sweep is authoritative.
    rows = parse_rtapp.parse_log(str(log), 0)
    with open(jobs, "w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=parse_rtapp.OUT_HEADER)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="offline analysis for a Model 1 timeblock")
    ap.add_argument("--timeblock", required=True, help="e.g. tb-20260707-1200")
    ap.add_argument("--results-root", default=str(HERE / "results"))
    args = ap.parse_args()

    tb_dir = Path(args.results_root) / args.timeblock
    if not tb_dir.exists():
        print(f"ERROR: {tb_dir} not found", file=sys.stderr)
        return 1
    samples_dir = tb_dir / "samples"
    have_stream = samples_dir.exists()
    if not have_stream:
        print(f"WARN: {samples_dir} not found; covariate slicing will be skipped "
              f"(did the sweep finish and save the stream?)", file=sys.stderr)

    n = 0
    for cell_json in sorted(tb_dir.glob("*/U*/cell.json")):
        cell_dir = cell_json.parent
        meta = json.loads(cell_json.read_text())
        start_ns = meta.get("start_wall_ns")
        end_ns = meta.get("end_wall_ns")

        ensure_jobs_csv(cell_dir)

        if have_stream and start_ns is not None and end_ns is not None:
            slice_cell(samples_dir, cell_dir, int(start_ns), int(end_ns))
            note = f"window=({start_ns},{end_ns})"
        else:
            note = "no covariate slice"
        n += 1
        print(f"[analyze] {cell_dir.relative_to(tb_dir)}  {note}")

    print(f"[analyze] processed {n} cell(s) in {tb_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
