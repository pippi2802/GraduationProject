"""Sequence metrics for periodic real-time traces: (m,k), consecutive misses,
burstiness. Shared by analyze.py and replay.py so the definitions can't
drift between them.

All functions take a 1D boolean array `miss` (True = deadline missed /
activation skipped) for ONE instance's own job sequence, in job order. Never
concatenate sequences from different instances before calling these: the
metrics are defined over one task's schedule.
"""
from __future__ import annotations

import numpy as np


def mk_worst(miss: np.ndarray, k: int) -> int | None:
    """Worst-case (m,k): minimum number of MET deadlines in any window of k
    consecutive activations. None if the sequence is shorter than k."""
    n = len(miss)
    if n < k:
        return None
    met = (~np.asarray(miss, dtype=bool)).astype(np.int64)
    window = np.convolve(met, np.ones(k, dtype=np.int64), mode="valid")
    return int(window.min())


def max_consecutive_misses(miss: np.ndarray) -> int:
    """Longest run of consecutive True (missed) entries."""
    best = cur = 0
    for m in miss:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best


def burstiness_index(miss: np.ndarray, k: int) -> float | None:
    """(k - m) / (k * miss_rate), with m the worst-case (m,k) met count.
    None if the sequence has no misses (undefined) or is shorter than k."""
    miss = np.asarray(miss, dtype=bool)
    miss_rate = float(np.mean(miss)) if len(miss) else 0.0
    if miss_rate == 0.0:
        return None
    m = mk_worst(miss, k)
    if m is None:
        return None
    return (k - m) / (k * miss_rate)


def cluster_exceedances(miss: np.ndarray, r: int = 5) -> int:
    """Number of clusters of missed jobs, where misses fewer than r
    activations apart belong to the same cluster (declustering, as used for
    extreme-value dependence and for the held-out validation test)."""
    miss_idx = np.flatnonzero(np.asarray(miss, dtype=bool))
    if len(miss_idx) == 0:
        return 0
    clusters = 1
    for prev, cur in zip(miss_idx[:-1], miss_idx[1:]):
        if cur - prev >= r:
            clusters += 1
    return clusters
