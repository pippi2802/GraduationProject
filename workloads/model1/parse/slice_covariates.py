#!/usr/bin/env python3
"""
Slice the continuous sampler streams (server.csv / covariates.csv, written by
the long-lived DaemonSet) into a single cell's [start,end] wall window.

The orchestrator records each cell's start/end wall-clock (CLOCK_REALTIME ns) in
cell.json; this cuts the rows whose ts_wall_ns falls in that window into the
cell's results directory.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def slice_csv(src: str, dst: str, start_ns: int, end_ns: int) -> int:
    n = 0
    with open(src, newline="", encoding="utf-8") as fin:
        reader = csv.reader(fin)
        rows = iter(reader)
        try:
            header = next(rows)
        except StopIteration:
            return 0
        try:
            wcol = header.index("ts_wall_ns")
        except ValueError:
            sys.stderr.write(f"WARN: no ts_wall_ns column in {src}\n")
            return 0
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "w", newline="", encoding="utf-8") as fout:
            w = csv.writer(fout)
            w.writerow(header)
            for row in rows:
                if len(row) <= wcol:
                    continue
                try:
                    ts = int(row[wcol])
                except ValueError:
                    continue
                if start_ns <= ts <= end_ns:
                    w.writerow(row)
                    n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="slice sampler streams into a cell window")
    ap.add_argument("--samples-dir", required=True, help="dir with server.csv/covariates.csv")
    ap.add_argument("--out-dir", required=True, help="cell results dir")
    ap.add_argument("--start-wall-ns", type=int, required=True)
    ap.add_argument("--end-wall-ns", type=int, required=True)
    args = ap.parse_args()

    src = Path(args.samples_dir)
    out = Path(args.out_dir)
    total = 0
    for name in ("server.csv", "covariates.csv"):
        s = src / name
        if s.exists():
            n = slice_csv(str(s), str(out / name), args.start_wall_ns, args.end_wall_ns)
            sys.stderr.write(f"sliced {n} rows -> {out / name}\n")
            total += n
        else:
            sys.stderr.write(f"WARN: {s} missing\n")
    return 0 if total >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
