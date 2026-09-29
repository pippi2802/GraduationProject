import numpy as np

from rq2.common.metrics import burstiness_index, cluster_exceedances, max_consecutive_misses, mk_worst


def test_mk_worst_hand_made():
    miss = np.array([False] * 45 + [True] * 5 + [False] * 50)  # 100 activations
    assert mk_worst(miss, 50) == 45
    assert mk_worst(miss, 200) is None  # sequence shorter than k


def test_max_consecutive_misses():
    miss = np.array([False] * 45 + [True] * 5 + [False] * 50)
    assert max_consecutive_misses(miss) == 5
    assert max_consecutive_misses(np.array([], dtype=bool)) == 0


def test_burstiness_index():
    miss = np.array([False] * 45 + [True] * 5 + [False] * 50)
    b = burstiness_index(miss, 50)
    expected = (50 - 45) / (50 * (5 / 100))
    assert abs(b - expected) < 1e-9

    no_miss = np.array([False] * 100)
    assert burstiness_index(no_miss, 50) is None


def test_cluster_exceedances():
    miss = np.array([False] * 10 + [True, True, True] + [False] * 10 + [True] + [False] * 10)
    # first three misses at indices 10,11,12 are one cluster (gap<5);
    # the lone miss at index 23 is a separate cluster (gap = 23-12 = 11 >= 5)
    assert cluster_exceedances(miss, r=5) == 2
    assert cluster_exceedances(np.array([False] * 10)) == 0
