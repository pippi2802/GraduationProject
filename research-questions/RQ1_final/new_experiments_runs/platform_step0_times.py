#!/usr/bin/env python3
"""PLATFORM STEP 0 - wall-clock start time of every run and the time span of every round.

The rerun files carry no wall-clock time in this copy (checkout time only). The real times exist on cp-0 as file modification times:
placement.json is written when a cell starts, jobs.csv when its rows are collected (end). Create the input on cp-0 with:

    cd ~/GraduationProject/research-questions/RQ1_final/os-experiments/test-results
    echo "run,start_epoch,end_epoch" > run_times.csv
    for d in results/*/*/*/; do d=${d%/}; echo "$d,$(stat -c %Y $d/placement.json),$(stat -c %Y $d/jobs.csv)"; done >> run_times.csv

then put run_times.csv into new_experiments_runs/input/ (commit + pull). This script reads it and writes
output/platform/platform_run_times.csv (one row per run) and output/platform/platform_round_spans.csv (one row per round and node placement).
"""
import sys

import pandas as pd

import common as cm

OUTP = cm.OUT / "platform"
SRC = cm.HERE / "input" / "run_times.csv"


def main():
    if not SRC.is_file():
        print(f"step 0 (times): {SRC} not found. Create it on cp-0 with the command in the docstring of platform_step0_times.py.")
        return 2
    OUTP.mkdir(parents=True, exist_ok=True)
    t = pd.read_csv(SRC)
    parts = t.run.str.split("/", expand=True)                    # results/<folder>_round<N>/<scale>/U<u>
    t["folder"], t["scale"], t["U"] = parts[1], parts[2], parts[3].str[1:].astype(float)
    t["round"] = t.folder.str.extract(r"_round(\d+)$")[0].astype(int)
    t["config_folder"] = t.folder.str.replace(r"_round\d+$", "", regex=True)
    for c in ("start_epoch", "end_epoch"):
        t[c.replace("epoch", "utc")] = pd.to_datetime(t[c], unit="s", utc=True)
    t["duration_min"] = (t.end_epoch - t.start_epoch) / 60.0
    t.sort_values(["round", "start_epoch"]).to_csv(OUTP / "platform_run_times.csv", index=False)
    g = t.groupby("round").agg(first_start=("start_utc", "min"), last_end=("end_utc", "max"), n_runs=("run", "count"))
    g["span_hours"] = (g.last_end - g.first_start).dt.total_seconds() / 3600.0
    g.reset_index().to_csv(OUTP / "platform_round_spans.csv", index=False)
    print(g.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
