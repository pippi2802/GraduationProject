"""Pure(ish) check functions for the profiling session runner (session.py).

Every check returns a CheckResult (name, status in {PASS, WARN, FAIL},
detail). Functions take already-collected data (strings, parsed rows,
sample dicts) rather than doing I/O themselves, so they can be tested
against fake /proc/stat, ps, /proc/interrupts and CSV content without a
real machine or cluster.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.stats import binom

# Kernel per-CPU housekeeping threads that are expected to show up pinned to
# any core, including isolated RT cores - never a symptom of stray work.
ALLOWED_KERNEL_THREAD_PATTERNS = [
    re.compile(r"^kworker/\d+"), re.compile(r"^ksoftirqd/\d+"), re.compile(r"^migration/\d+"),
    re.compile(r"^rcu"), re.compile(r"^cpuhp/\d+"), re.compile(r"^idle"),
]


@dataclass
class CheckResult:
    name: str
    status: str  # PASS | WARN | FAIL
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def result(name: str, ok: bool, detail: str = "", warn: bool = False) -> CheckResult:
    status = "PASS" if ok else ("WARN" if warn else "FAIL")
    return CheckResult(name, status, detail)


# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------

def check_cpu_count(online_cpus: list[int], expected: int = 4) -> CheckResult:
    ok = len(online_cpus) == expected
    return result("cpu_count", ok, f"{len(online_cpus)} online cpus (expected {expected})")


def check_threads_per_core(threads_per_core: int, expected: int = 1) -> CheckResult:
    ok = threads_per_core == expected
    return result("threads_per_core", ok, f"{threads_per_core} thread(s)/core (expected {expected}, SMT off)")


def check_isolation_cmdline(cmdline: str, rt_cores: list[int]) -> CheckResult:
    wanted = ["isolcpus", "nohz_full", "rcu_nocbs"]
    present = [w for w in wanted if w in cmdline]
    missing = [w for w in wanted if w not in cmdline]
    if not missing:
        return result("isolation_cmdline", True, f"present: {present}")
    return result("isolation_cmdline", False, f"missing: {missing} (present: {present})", warn=True)


def check_stray_threads(ps_output: str, rt_cores: list[int]) -> CheckResult:
    """ps_output: `ps -eLo pid,tid,psr,comm` text, header line included."""
    stray = []
    for line in ps_output.splitlines()[1:]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        _, _, psr, comm = parts
        try:
            psr = int(psr)
        except ValueError:
            continue
        if psr not in rt_cores:
            continue
        if any(p.match(comm) for p in ALLOWED_KERNEL_THREAD_PATTERNS):
            continue
        stray.append(f"{comm}@cpu{psr}")
    ok = not stray
    return result("stray_threads_on_rt_cores", ok, f"stray: {stray}" if stray else "none")


def check_paths_present(paths: dict[str, bool]) -> CheckResult:
    """paths: {label: exists_bool}, e.g. {'enemy binary': True, 'clip': False}."""
    missing = [label for label, exists in paths.items() if not exists]
    return result("required_paths_present", not missing, f"missing: {missing}" if missing else "all present")


def check_results_dir_writable(writable: bool, path: str) -> CheckResult:
    return result("results_dir_writable", writable, path)


def check_llc_known(llc_size_kb: int | None) -> CheckResult:
    return result("llc_size_known", llc_size_kb is not None, f"llc_size_kb={llc_size_kb}")


# --------------------------------------------------------------------------
# During-run (sampled)
# --------------------------------------------------------------------------

def cpu_utilization_pct(prev_stat_line: str, curr_stat_line: str) -> float:
    """prev/curr: one `cpuN ...` line from /proc/stat. Returns non-idle %."""
    prev = [int(x) for x in prev_stat_line.split()[1:]]
    curr = [int(x) for x in curr_stat_line.split()[1:]]
    d = [c - p for c, p in zip(curr, prev)]
    idle = d[3] + (d[4] if len(d) > 4 else 0)  # idle + iowait
    total = sum(d)
    if total <= 0:
        return 0.0
    return 100.0 * (total - idle) / total


def check_enemy_busy(prev_stat_line: str, curr_stat_line: str, threshold_pct: float = 95.0) -> CheckResult:
    util = cpu_utilization_pct(prev_stat_line, curr_stat_line)
    return result("enemy_core_utilization", util > threshold_pct, f"{util:.1f}% (threshold {threshold_pct}%)")


def check_cores_idle(prev_lines: dict[int, str], curr_lines: dict[int, str], threshold_pct: float = 5.0) -> CheckResult:
    utils = {cpu: cpu_utilization_pct(prev_lines[cpu], curr_lines[cpu]) for cpu in prev_lines}
    bad = {cpu: u for cpu, u in utils.items() if u >= threshold_pct}
    return result("non_task_cores_idle", not bad, f"utilizations={utils}")


def check_affinity(pid_psr: int, expected_cpu: int, label: str) -> CheckResult:
    return result(f"{label}_affinity", pid_psr == expected_cpu,
                  f"running on cpu{pid_psr}, expected cpu{expected_cpu}")


def check_no_stress_process(process_names: list[str]) -> CheckResult:
    return result("baseline_no_stress_process", not process_names, f"found: {process_names}")


def interrupt_deltas(prev_text: str, curr_text: str, cores: list[int]) -> dict[int, int]:
    """prev/curr: /proc/interrupts text. Sums the per-IRQ-line delta for each
    requested CPU column across all IRQ rows (a coarse but simple noise proxy)."""
    def parse(text: str) -> dict[int, list[int]]:
        lines = text.splitlines()
        header = lines[0].split()
        cpu_cols = [i for i, h in enumerate(header) if h.startswith("CPU")]
        per_irq: dict[int, list[int]] = {}
        for i, line in enumerate(lines[1:]):
            fields = line.split()
            if len(fields) <= max(cpu_cols, default=-1):
                continue
            try:
                per_irq[i] = [int(fields[c + 1]) for c in cpu_cols]
            except (ValueError, IndexError):
                continue
        return per_irq

    prev, curr = parse(prev_text), parse(curr_text)
    totals = {cpu: 0 for cpu in cores}
    for irq, curr_vals in curr.items():
        prev_vals = prev.get(irq)
        if prev_vals is None:
            continue
        for cpu in cores:
            if cpu < len(curr_vals) and cpu < len(prev_vals):
                totals[cpu] += max(0, curr_vals[cpu] - prev_vals[cpu])
    return totals


def check_interrupt_load(prev_text: str, curr_text: str, cores: list[int], warn_threshold: int = 1000) -> CheckResult:
    deltas = interrupt_deltas(prev_text, curr_text, cores)
    high = {c: d for c, d in deltas.items() if d > warn_threshold}
    return result("interrupt_deltas_on_rt_cores", not high, f"deltas={deltas}", warn=True) if high else \
        result("interrupt_deltas_on_rt_cores", True, f"deltas={deltas}")


def steal_pct(prev_stat_line: str, curr_stat_line: str) -> float:
    prev = [int(x) for x in prev_stat_line.split()[1:]]
    curr = [int(x) for x in curr_stat_line.split()[1:]]
    d = [c - p for c, p in zip(curr, prev)]
    steal = d[7] if len(d) > 7 else 0
    total = sum(d)
    return 100.0 * steal / total if total > 0 else 0.0


def check_steal_time(prev_stat_line: str, curr_stat_line: str) -> CheckResult:
    pct = steal_pct(prev_stat_line, curr_stat_line)
    return result("steal_time", True, f"{pct:.2f}%")  # reported, not a pass/fail gate


# --------------------------------------------------------------------------
# Post-run data checks
# --------------------------------------------------------------------------

def check_row_count(rows: list[dict], expected_jobs: int) -> CheckResult:
    """rt_video.py never logs warm-up jobs (they run before the logged
    periodic loop, whose log arrays are sized `--jobs` only), so the row
    count is exactly `expected_jobs` regardless of `--warmup-jobs`."""
    ok = len(rows) == expected_jobs
    return result("row_count", ok, f"{len(rows)} rows (expected {expected_jobs})")


def check_multi_instance_alignment(first_release_ns_by_instance: dict[str, int], tol_ns: float = 1e6) -> CheckResult:
    values = list(first_release_ns_by_instance.values())
    if len(values) < 2:
        return result("multi_instance_start_alignment", True, "single instance, n/a")
    spread = max(values) - min(values)
    return result("multi_instance_start_alignment", spread <= tol_ns,
                  f"spread={spread}ns (tol={tol_ns}ns)")


def check_no_skips(rows: list[dict]) -> CheckResult:
    n_skipped = sum(1 for r in rows if r.get("skipped") == "1")
    return result("no_skipped_jobs", n_skipped == 0, f"{n_skipped} skipped")


def check_release_spacing(release_ns: list[int], period_ns: float, tol_frac: float = 0.02) -> CheckResult:
    diffs = np.diff(np.asarray(release_ns, dtype=np.float64))
    dev = np.abs(diffs - period_ns)
    max_dev = float(np.max(dev)) if len(dev) else 0.0
    ok = max_dev <= tol_frac * period_ns
    return result("release_spacing", ok, f"max deviation {max_dev:.0f}ns (tol {tol_frac * period_ns:.0f}ns)")


def check_timing_sanity(rows: list[dict]) -> CheckResult:
    bad = 0
    for r in rows:
        if r.get("skipped") == "1" or r.get("cpu_ns", "") == "":
            continue
        cpu_ns, response_ns, wait_ns = int(r["cpu_ns"]), int(r["response_ns"]), int(r["wait_ns"])
        if not (cpu_ns > 0 and response_ns >= cpu_ns and wait_ns >= 0):
            bad += 1
    return result("timing_sanity", bad == 0, f"{bad} rows fail cpu_ns>0 / response>=cpu / wait>=0")


def check_metadata_flags(meta: dict) -> CheckResult:
    flags = {"mlockall_ok": meta.get("mlockall_ok"), "sched_fifo_ok": meta.get("sched_fifo_ok"),
             "affinity_ok": meta.get("affinity_ok")}
    ok = all(flags.values())
    return result("realtime_setup_flags", bool(ok), str(flags))


def check_stalls(cpu_ns: np.ndarray, period_ns: float, stall_factor: float = 2.0) -> CheckResult:
    n_stalls = int(np.sum(cpu_ns > stall_factor * period_ns))
    return result("vm_stalls", n_stalls == 0, f"{n_stalls} jobs > {stall_factor}x period", warn=True) \
        if n_stalls else result("vm_stalls", True, "0 jobs > stall threshold")


def _half_split_stats(cpu_ns: np.ndarray) -> tuple[float, float, float, float]:
    mid = len(cpu_ns) // 2
    first, second = cpu_ns[:mid], cpu_ns[mid:]
    return (float(np.median(first)), float(np.percentile(first, 99)),
            float(np.median(second)), float(np.percentile(second, 99)))


def check_stationarity(cpu_ns: np.ndarray, threshold_pct: float = 5.0) -> CheckResult:
    if len(cpu_ns) < 4:
        return result("stationarity", True, "too few samples, skipped")
    med1, p99_1, med2, p99_2 = _half_split_stats(cpu_ns)
    med_rel = 100 * abs(med2 - med1) / med1 if med1 else 0.0
    p99_rel = 100 * abs(p99_2 - p99_1) / p99_1 if p99_1 else 0.0
    ok = med_rel <= threshold_pct and p99_rel <= threshold_pct
    return result("stationarity", ok, f"median drift {med_rel:.1f}%, p99 drift {p99_rel:.1f}%", warn=True) \
        if not ok else result("stationarity", True, f"median drift {med_rel:.1f}%, p99 drift {p99_rel:.1f}%")


def check_interference_effect(baseline_cpu_ns: np.ndarray, condition_cpu_ns: np.ndarray,
                               threshold: float = 1.02) -> CheckResult:
    med_ratio = float(np.median(condition_cpu_ns) / np.median(baseline_cpu_ns))
    p99_ratio = float(np.percentile(condition_cpu_ns, 99) / np.percentile(baseline_cpu_ns, 99))
    measurable = med_ratio >= threshold or p99_ratio >= threshold
    detail = f"median ratio={med_ratio:.3f}, p99 ratio={p99_ratio:.3f}"
    if measurable:
        return result("interference_effect", True, detail)
    return result("interference_effect", False, "no measurable interference effect: " + detail, warn=True)


def check_baseline_drift(baseline_cpu_ns: np.ndarray, baseline_end_cpu_ns: np.ndarray,
                          threshold_pct: float = 5.0) -> CheckResult:
    med_rel = 100 * abs(np.median(baseline_end_cpu_ns) - np.median(baseline_cpu_ns)) / np.median(baseline_cpu_ns)
    p99_rel = 100 * abs(np.percentile(baseline_end_cpu_ns, 99) - np.percentile(baseline_cpu_ns, 99)) / \
        np.percentile(baseline_cpu_ns, 99)
    ok = med_rel <= threshold_pct and p99_rel <= threshold_pct
    detail = f"median drift {med_rel:.1f}%, p99 drift {p99_rel:.1f}%"
    return result("baseline_vs_baseline_end_drift", ok, detail, warn=True) if not ok else \
        result("baseline_vs_baseline_end_drift", True, detail)


# --------------------------------------------------------------------------
# Enemy effectiveness (distribution-free percentile CI, order-statistic /
# binomial method - same family of method as Step 2's Method A bound)
# --------------------------------------------------------------------------

def percentile_with_ci(samples: np.ndarray, q: float, confidence: float = 0.95) -> tuple[float, float, float]:
    x = np.sort(np.asarray(samples, dtype=np.float64))
    n = len(x)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    point = float(np.percentile(x, q * 100))
    alpha = 1 - confidence
    lo_rank = max(1, int(binom.ppf(alpha / 2, n, q)))
    hi_rank = min(n, int(binom.ppf(1 - alpha / 2, n, q)) + 1)
    return point, float(x[lo_rank - 1]), float(x[hi_rank - 1])


def enemy_effectiveness_summary(cache_alone: np.ndarray, cache_enemy: np.ndarray,
                                 memory_alone: np.ndarray, memory_enemy: np.ndarray,
                                 slowdown_threshold: float = 1.05) -> dict[str, Any]:
    """Each condition is matched against its own victim's alone baseline
    (cache victim vs cache enemy, memory victim vs memory enemy), since the
    two victims use different buffer sizes (LLC vs 10x LLC)."""
    samples = {"cache_alone": cache_alone, "cache_enemy": cache_enemy,
               "memory_alone": memory_alone, "memory_enemy": memory_enemy}
    summary: dict[str, Any] = {}
    for label, sample in samples.items():
        med, _, _ = percentile_with_ci(sample, 0.5)
        p90, p90_lo, p90_hi = percentile_with_ci(sample, 0.9)
        summary[label] = {"median": med, "p90": p90, "p90_ci": [p90_lo, p90_hi], "n": len(sample)}

    for kind in ("cache", "memory"):
        slowdown = summary[f"{kind}_enemy"]["p90"] / summary[f"{kind}_alone"]["p90"]
        summary[f"{kind}_enemy"]["slowdown_p90"] = slowdown
        summary[f"{kind}_enemy"]["status"] = "PASS" if slowdown > slowdown_threshold else "WARN"
    return summary
