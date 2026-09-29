import numpy as np

from rq2.orchestration import checks

# --- preflight --------------------------------------------------------

def test_check_cpu_count():
    assert checks.check_cpu_count([0, 1, 2, 3], expected=4).status == "PASS"
    assert checks.check_cpu_count([0, 1], expected=4).status == "FAIL"


def test_check_isolation_cmdline():
    full = "BOOT_IMAGE=... isolcpus=1-3 nohz_full=1-3 rcu_nocbs=1-3"
    assert checks.check_isolation_cmdline(full, [1, 2, 3]).status == "PASS"
    partial = "BOOT_IMAGE=... isolcpus=1-3"
    r = checks.check_isolation_cmdline(partial, [1, 2, 3])
    assert r.status == "WARN"
    assert "nohz_full" in r.detail


PS_HEADER = "    PID     TID PSR COMMAND"


def test_check_stray_threads_flags_only_non_kernel_on_rt_cores():
    ps_output = "\n".join([
        PS_HEADER,
        "      1       1   0 systemd",
        "     10      10   1 kworker/1:0",
        "     11      11   1 rcu_sched",
        "   1234    1234   2 my_stray_process",
        "   5555    5555   0 python3",  # cpu0 is not an RT core: ignored
    ])
    r = checks.check_stray_threads(ps_output, rt_cores=[1, 2, 3])
    assert r.status == "FAIL"
    assert "my_stray_process@cpu2" in r.detail

    clean = "\n".join([PS_HEADER, "     10      10   1 kworker/1:0", "     11      11   2 migration/2"])
    assert checks.check_stray_threads(clean, rt_cores=[1, 2, 3]).status == "PASS"


# --- during-run (utilization / interrupts) -----------------------------

def stat_line(cpu, user, idle):
    return f"cpu{cpu} {user} 0 0 {idle} 0 0 0 0 0 0"


def test_cpu_utilization_and_enemy_busy():
    prev = stat_line(2, user=0, idle=0)
    curr = stat_line(2, user=1000, idle=10)  # ~99% busy
    assert checks.check_enemy_busy(prev, curr, threshold_pct=95.0).status == "PASS"

    curr_idle = stat_line(2, user=10, idle=1000)  # ~1% busy
    assert checks.check_enemy_busy(prev, curr_idle, threshold_pct=95.0).status == "FAIL"


def test_check_cores_idle():
    prev = {2: stat_line(2, 0, 0), 3: stat_line(3, 0, 0)}
    curr_idle = {2: stat_line(2, 10, 1000), 3: stat_line(3, 5, 1000)}
    assert checks.check_cores_idle(prev, curr_idle, threshold_pct=5.0).status == "PASS"

    curr_busy = {2: stat_line(2, 900, 100), 3: stat_line(3, 5, 1000)}
    r = checks.check_cores_idle(prev, curr_busy, threshold_pct=5.0)
    assert r.status == "FAIL"
    assert "2" in r.detail


def interrupts_text(counts_by_cpu):
    header = "           CPU0       CPU1       CPU2       CPU3"
    row = " 24: " + "  ".join(str(counts_by_cpu.get(c, 0)) for c in range(4)) + "   PCI-MSI  edge  eth0"
    return header + "\n" + row


def test_interrupt_deltas():
    prev = interrupts_text({0: 100, 1: 100, 2: 100, 3: 100})
    curr = interrupts_text({0: 150, 1: 100, 2: 100, 3: 2000})
    deltas = checks.interrupt_deltas(prev, curr, cores=[1, 2, 3])
    assert deltas[1] == 0
    assert deltas[3] == 1900
    r = checks.check_interrupt_load(prev, curr, cores=[1, 2, 3], warn_threshold=1000)
    assert r.status == "WARN"


# --- post-run data checks ----------------------------------------------

def make_rows(n, skipped_idx=(), cpu_ns=1_000_000, period_ns=33_300_000, response_ns=None, wait_ns=1000):
    rows = []
    response_ns = response_ns if response_ns is not None else cpu_ns + 100_000
    for i in range(n):
        if i in skipped_idx:
            rows.append({"job_id": str(i), "release_ns": str(i * period_ns), "skipped": "1",
                         "deadline_met": "0", "cpu_ns": "", "response_ns": "", "wait_ns": ""})
        else:
            rows.append({"job_id": str(i), "release_ns": str(i * period_ns), "skipped": "0",
                         "deadline_met": "1", "cpu_ns": str(cpu_ns), "response_ns": str(response_ns),
                         "wait_ns": str(wait_ns)})
    return rows


def test_check_row_count():
    rows = make_rows(100)
    assert checks.check_row_count(rows, expected_jobs=100).status == "PASS"
    assert checks.check_row_count(rows, expected_jobs=90).status == "FAIL"


def test_check_no_skips():
    assert checks.check_no_skips(make_rows(10)).status == "PASS"
    assert checks.check_no_skips(make_rows(10, skipped_idx=(3, 5))).status == "FAIL"


def test_check_release_spacing():
    period_ns = 33_300_000
    good = [i * period_ns for i in range(20)]
    assert checks.check_release_spacing(good, period_ns, tol_frac=0.02).status == "PASS"
    bad = list(good)
    bad[10] += int(0.5 * period_ns)
    assert checks.check_release_spacing(bad, period_ns, tol_frac=0.02).status == "FAIL"


def test_check_timing_sanity():
    rows = make_rows(10)
    assert checks.check_timing_sanity(rows).status == "PASS"
    bad_rows = make_rows(10, response_ns=500)  # response < cpu_ns=1_000_000
    assert checks.check_timing_sanity(bad_rows).status == "FAIL"


def test_check_metadata_flags():
    ok = {"mlockall_ok": True, "sched_fifo_ok": True, "affinity_ok": True}
    assert checks.check_metadata_flags(ok).status == "PASS"
    bad = {"mlockall_ok": True, "sched_fifo_ok": False, "affinity_ok": True}
    assert checks.check_metadata_flags(bad).status == "FAIL"


def test_check_multi_instance_alignment():
    aligned = {"instance0": 1_000_000_000, "instance1": 1_000_050_000}
    assert checks.check_multi_instance_alignment(aligned, tol_ns=1e6).status == "PASS"
    misaligned = {"instance0": 1_000_000_000, "instance1": 1_100_000_000}
    assert checks.check_multi_instance_alignment(misaligned, tol_ns=1e6).status == "FAIL"


def test_check_stalls():
    cpu_ns = np.full(100, 1_000_000.0)
    period_ns = 10_000_000.0
    assert checks.check_stalls(cpu_ns, period_ns, stall_factor=2.0).status == "PASS"
    cpu_ns_with_stall = cpu_ns.copy()
    cpu_ns_with_stall[5] = 30_000_000.0
    assert checks.check_stalls(cpu_ns_with_stall, period_ns, stall_factor=2.0).status == "WARN"


def test_check_stationarity_drifting_halves():
    stable = np.random.default_rng(0).normal(1_000_000, 1000, 200)
    assert checks.check_stationarity(stable, threshold_pct=5.0).status == "PASS"

    drifting = np.concatenate([np.full(100, 1_000_000.0), np.full(100, 1_300_000.0)])
    assert checks.check_stationarity(drifting, threshold_pct=5.0).status == "WARN"


def test_check_interference_effect():
    baseline = np.full(200, 1_000_000.0)
    no_effect = np.full(200, 1_005_000.0)  # 0.5% higher: below threshold
    assert checks.check_interference_effect(baseline, no_effect, threshold=1.02).status == "WARN"
    with_effect = np.full(200, 1_100_000.0)  # 10% higher
    assert checks.check_interference_effect(baseline, with_effect, threshold=1.02).status == "PASS"


def test_check_baseline_drift():
    baseline = np.full(200, 1_000_000.0)
    stable_end = np.full(200, 1_010_000.0)  # 1% drift
    assert checks.check_baseline_drift(baseline, stable_end, threshold_pct=5.0).status == "PASS"
    drifted_end = np.full(200, 1_200_000.0)  # 20% drift
    assert checks.check_baseline_drift(baseline, drifted_end, threshold_pct=5.0).status == "WARN"


# --- enemy effectiveness -------------------------------------------------

def test_percentile_with_ci_bounds_contain_point():
    rng = np.random.default_rng(1)
    samples = rng.normal(100, 5, 500)
    point, lo, hi = checks.percentile_with_ci(samples, 0.9, confidence=0.95)
    assert lo <= point <= hi


def test_enemy_effectiveness_summary_pass_and_warn():
    rng = np.random.default_rng(2)
    cache_alone = rng.normal(100, 2, 30)
    cache_enemy = rng.normal(130, 2, 30)  # clear slowdown
    memory_alone = rng.normal(100, 2, 30)
    memory_enemy = rng.normal(101, 2, 30)  # negligible slowdown
    summary = checks.enemy_effectiveness_summary(cache_alone, cache_enemy, memory_alone, memory_enemy,
                                                  slowdown_threshold=1.05)
    assert summary["cache_enemy"]["status"] == "PASS"
    assert summary["memory_enemy"]["status"] == "WARN"
