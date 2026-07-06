#!/usr/bin/env python3
"""Load per-job JSONL metrics into a pandas DataFrame.

Reads either a single ``.jsonl`` file or, recursively, all ``.jsonl`` files
under a directory (e.g. ``results/`` containing ``rtdra/`` and ``vanilla/``).

Use as a library (``load(...)``) or as a CLI that writes a combined CSV.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import pandas as pd

EXPECTED_COLUMNS = [
    "record", "run_id", "mode", "taskset_id", "task_id", "job_index",
    "release_ts_ns", "start_ts_ns", "completion_ts_ns",
    "exec_time_us", "response_time_us", "wait_time_us", "preempt_us",
    "steal_us", "throttled_us", "cpu_id",
    "target_c_us", "period_t_us",
    "deadline_us", "overrun", "deadline_miss", "tardiness_us",
    "budget_q_us", "period_p_us", "cores_m", "util", "n_tasks",
    "interference", "node", "kernel",
    # run-level summary fields (present only on record=="summary" rows)
    "steal_pct", "wall_us", "iters_per_us", "nr_throttled",
]


def _iter_files(path: str):
    if os.path.isdir(path):
        yield from sorted(glob.glob(os.path.join(path, "**", "*.jsonl"), recursive=True))
    else:
        yield path


def load(path: str) -> pd.DataFrame:
    """Load all JSONL records under `path` into a DataFrame."""
    rows = []
    for fp in _iter_files(path):
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    if not rows:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    df = pd.DataFrame(rows)
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    # Records written before the "record" field existed are job rows.
    df["record"] = df["record"].fillna("job")
    return df


def split(df: pd.DataFrame):
    """Separate per-job rows from run-level summary rows.

    Returns (jobs_df, summary_df). The per-job frame is augmented with the
    run's ``steal_pct`` (joined on run_id) so cloud-steal can be correlated
    with deadline/supply outcomes at the job level.
    """
    jobs = df[df["record"] == "job"].copy()
    summaries = df[df["record"] == "summary"].copy()
    if not summaries.empty and not jobs.empty:
        steal = summaries[["run_id", "steal_pct"]].drop_duplicates("run_id")
        jobs = jobs.drop(columns=["steal_pct"], errors="ignore").merge(
            steal, on="run_id", how="left")
    return jobs, summaries



def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Parse benchmark JSONL into a CSV")
    p.add_argument("path", help="JSONL file or results directory")
    p.add_argument("--out", default="jobs.csv", help="output CSV path")
    args = p.parse_args(argv)

    df = load(args.path)
    if df.empty:
        print("no records found", file=sys.stderr)
        return 1
    df.to_csv(args.out, index=False)
    print(f"loaded {len(df)} jobs from {args.path} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
