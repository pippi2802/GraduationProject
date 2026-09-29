"""Loading rt_video.py CSV traces + their metadata JSON, shared by every
analysis stage so the CSV schema (rq2/workload/rt_video.py's output) and the
warm-up/instance-grouping/VM-stall conventions are defined once.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


def load_csv_rows(path: Path | str) -> list[dict[str, str]]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_metadata(path: Path | str) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def metadata_path_for(csv_path: Path | str) -> Path:
    """rt_video.py writes <stem>.meta.json next to <stem>.csv."""
    csv_path = Path(csv_path)
    return csv_path.with_suffix("").with_suffix(".meta.json")


def group_by_instance(rows: list[dict[str, str]], exclude_warmup: bool = True) -> dict[str, list[dict[str, str]]]:
    by_instance: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        if exclude_warmup and r.get("warmup", "0") == "1":
            continue
        by_instance[r["instance_id"]].append(r)
    for instance_id, inst_rows in by_instance.items():
        inst_rows.sort(key=lambda r: int(r["job_id"]))
    return dict(by_instance)


def cpu_ns_array(rows: list[dict[str, str]]) -> np.ndarray:
    """cpu_ns for non-skipped rows, in job order, as float64 nanoseconds."""
    return np.array([int(r["cpu_ns"]) for r in rows if r.get("cpu_ns", "") != ""], dtype=np.float64)


def miss_array(rows: list[dict[str, str]]) -> np.ndarray:
    """Boolean miss sequence (True = missed/skipped) including skipped rows,
    in job order - the sequence sequence metrics in rq2.common.metrics need."""
    return np.array([r["deadline_met"] != "1" for r in rows], dtype=bool)


def split_stalls(cpu_ns: np.ndarray, period_ns: float, stall_factor: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Split cpu_ns into (fitting, stalls): jobs with cpu_ns > stall_factor *
    period_ns are treated as VM stalls, excluded from tail fitting and
    reported separately rather than silently dropped."""
    threshold = stall_factor * period_ns
    is_stall = cpu_ns > threshold
    return cpu_ns[~is_stall], cpu_ns[is_stall]


def period_ns_from_rows(rows: list[dict[str, str]]) -> float | None:
    if len(rows) < 2:
        return None
    releases = sorted(int(r["release_ns"]) for r in rows[:2])
    return float(releases[1] - releases[0])
