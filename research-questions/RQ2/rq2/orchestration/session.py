"""Unattended profiling session runner.

preflight -> platform info -> enemy-effectiveness test -> ordered runs
(baseline/cache/memory/baseline_end) per deployment -> per-run checks ->
session_report.json/md. Reuses rq2.orchestration.campaign.Campaign for
interference start/stop and pod deploy/wait/delete instead of
reimplementing them; session.py adds preflight/monitoring/post-run checks,
retry-once, and the session-level report on top.

Assumes it runs ON the worker VM being profiled (like tools/platform_info.sh
and stress/enemy_effectiveness.sh, its OS-facing checks read local
/proc, ps, lscpu directly) - pod deployment itself still goes through
NodeExecutor for --dry-run consistency with campaign.py.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform as platform_module
import subprocess
import threading
import time
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from rq2.common.io import cpu_ns_array, load_csv_rows, load_metadata
from rq2.common.manifest import finish_manifest, read_manifest, start_manifest, write_manifest
from rq2.common.paths import find_rq2_root, raw_run_dir, results_root, session_log_path, session_raw_dir
from rq2.orchestration import checks
from rq2.orchestration.campaign import Campaign
from rq2.orchestration.node_exec import NodeExecutor

RT_CORES_DEFAULT = [1, 2, 3]
IMDS_URL = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"


def load_session_config(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def _sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError) as e:
        return f"<error: {e}>"


def parse_cpu_list(text: str) -> list[int]:
    cpus: list[int] = []
    for part in text.strip().split(","):
        if "-" in part:
            lo, hi = part.split("-")
            cpus.extend(range(int(lo), int(hi) + 1))
        elif part:
            cpus.append(int(part))
    return cpus


def read_platform_yaml(rq2_root: Path) -> dict[str, Any]:
    with open(rq2_root / "configs" / "platform.yaml") as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------
# Platform info
# --------------------------------------------------------------------------

def capture_platform_info(rq2_root: Path, output_path: Path, dry_run: bool) -> dict[str, Any] | None:
    script = rq2_root / "tools" / "platform_info.sh"
    if dry_run:
        print(f"[dry-run] capture platform info -> {output_path}"
              f" (via {script.name})" if script.exists() else " (python fallback)")
        return None
    if script.exists():
        subprocess.run([str(script), "--output", str(output_path)], check=True)
        return json.loads(output_path.read_text())
    return _platform_info_fallback(output_path)


def _platform_info_fallback(output_path: Path) -> dict[str, Any]:
    lscpu_text = _sh(["lscpu"])
    cpu_model = None
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if line.lower().startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    threads_per_core = None
    for line in lscpu_text.splitlines():
        if line.startswith("Thread(s) per core"):
            threads_per_core = line.split(":", 1)[1].strip()
    cmdline = Path("/proc/cmdline").read_text().strip() if Path("/proc/cmdline").exists() else ""
    vm_metadata = None
    try:
        req = urllib.request.Request(IMDS_URL, headers={"Metadata": "true"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            vm_metadata = json.loads(resp.read().decode())
    except Exception:
        vm_metadata = None
    info = {
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cpu_model": cpu_model, "threads_per_core": threads_per_core,
        "kernel_version": platform_module.release(), "kernel_cmdline": cmdline,
        "llc_size_kb": None, "lscpu": {"raw_text": lscpu_text}, "vm_metadata": vm_metadata,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(info, indent=2))
    return info


def _vm_id(info: dict[str, Any] | None) -> str | None:
    return ((info or {}).get("vm_metadata") or {}).get("compute", {}).get("vmId")


# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------

def run_preflight(rq2_root: Path, config: dict[str, Any], dry_run: bool) -> list[checks.CheckResult]:
    if dry_run:
        print("[dry-run] preflight: cpu count, threads/core, isolation cmdline, "
              "stray threads, required paths, results dir writable, LLC known")
        return []

    rt_cores = config.get("platform", {}).get("rt_cores", RT_CORES_DEFAULT)
    online = parse_cpu_list(Path("/sys/devices/system/cpu/online").read_text())
    lscpu_text = _sh(["lscpu"])
    tpc_line = next((l for l in lscpu_text.splitlines() if l.startswith("Thread(s) per core")), None)
    tpc = int(tpc_line.split(":", 1)[1].strip()) if tpc_line else -1
    cmdline = Path("/proc/cmdline").read_text() if Path("/proc/cmdline").exists() else ""
    ps_out = _sh(["ps", "-eLo", "pid,tid,psr,comm"])

    rq2_root_paths = {
        "enemy binary": (rq2_root / "stress" / "enemy").exists(),
        "victim binary": (rq2_root / "stress" / "victim").exists(),
        "pod template": (rq2_root / "templates" / "pod_template.yaml").exists(),
    }
    clip = config["workload"].get("input")
    if clip:
        rq2_root_paths["clip file"] = Path(clip).exists()

    results_dir = results_root(rq2_root)
    platform_cfg = read_platform_yaml(rq2_root)

    return [
        checks.check_cpu_count(online, expected=len(rt_cores) + 1),
        checks.check_threads_per_core(tpc, expected=1),
        checks.check_isolation_cmdline(cmdline, rt_cores),
        checks.check_stray_threads(ps_out, rt_cores),
        checks.check_paths_present(rq2_root_paths),
        checks.check_results_dir_writable(os.access(results_dir, os.W_OK), str(results_dir)),
        checks.check_llc_known(platform_cfg.get("llc_size_kb")),
    ]


# --------------------------------------------------------------------------
# Enemy effectiveness test
# --------------------------------------------------------------------------

def run_enemy_effectiveness(rq2_root: Path, config: dict[str, Any], session_dir: Path,
                             dry_run: bool) -> dict[str, Any] | None:
    ee_cfg = config.get("enemy_effectiveness", {})
    if not ee_cfg.get("enabled", True):
        return None

    llc_kb = read_platform_yaml(rq2_root).get("llc_size_kb")
    cache_kb = llc_kb
    memory_kb = (llc_kb or 0) * ee_cfg.get("memory_size_kb_multiplier", 10) if llc_kb else None
    enemy_cpus = ee_cfg.get("enemy_cpus") or [2, 3]
    output_csv = session_dir / "enemy_effectiveness.csv"

    cmd = [
        str(rq2_root / "stress" / "enemy_effectiveness.sh"),
        "--victim", str(rq2_root / "stress" / "victim"),
        "--enemy", str(rq2_root / "stress" / "enemy"),
        "--victim-cpu", str(ee_cfg.get("victim_cpu", 1)),
        "--enemy-cpus", ",".join(str(c) for c in enemy_cpus),
        "--cache-size-kb", str(cache_kb), "--memory-size-kb", str(memory_kb),
        "--stride-bytes", str(ee_cfg.get("stride_bytes", 64)),
        "--passes", str(ee_cfg.get("passes", 50)),
        "--trials", str(ee_cfg.get("trials", 30)),
        "--output", str(output_csv),
    ]
    if dry_run:
        cmd.append("--dry-run")
    subprocess.run(cmd, check=True)
    if dry_run:
        return None

    by_cond: dict[str, list[float]] = defaultdict(list)
    with open(output_csv, newline="") as f:
        for row in csv.DictReader(f):
            by_cond[row["condition"]].append(float(row["elapsed_ms"]))

    summary = checks.enemy_effectiveness_summary(
        np.array(by_cond["cache_alone"]), np.array(by_cond["cache_enemy"]),
        np.array(by_cond["memory_alone"]), np.array(by_cond["memory_enemy"]),
        slowdown_threshold=ee_cfg.get("slowdown_threshold", 1.05),
    )
    (session_dir / "enemy_effectiveness_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


# --------------------------------------------------------------------------
# Ordered runs
# --------------------------------------------------------------------------

def build_session_runs(config: dict[str, Any]) -> list[dict[str, Any]]:
    enemy_on_cpu0 = config.get("enemy_on_cpu0", False)
    runs = []
    for deployment, dep_cfg in config["deployments"].items():
        for run_spec in dep_cfg["runs"]:
            enemy = None
            if run_spec.get("enemy"):
                cpus = list(run_spec["enemy"]["cpus"])
                if enemy_on_cpu0 and 0 not in cpus:
                    cpus = cpus + [0]
                enemy = (run_spec["enemy"]["kind"], cpus)
            jobs = config["baseline_end_jobs"] if run_spec["name"] == "baseline_end" else config["jobs_per_run"]
            runs.append({
                "deployment": deployment, "instances": dep_cfg["instances"],
                "condition": run_spec["name"], "enemy": enemy, "hk_load": False,
                "mode": "profiling", "jobs": jobs,
            })
    return runs


# --------------------------------------------------------------------------
# Session
# --------------------------------------------------------------------------

class Session:
    def __init__(self, config: dict[str, Any], rq2_root: Path, dry_run: bool):
        self.config = config
        self.rq2_root = rq2_root
        self.dry_run = dry_run
        self.session_name = config["session"]
        self.session_dir = session_raw_dir(self.session_name, rq2_root)
        self.executor = NodeExecutor(dry_run=dry_run)
        campaign_config = {
            "workload": config["workload"],
            "enemy": config["enemy"],
            "housekeeping_load": {"enabled": False},
            "jobs_per_run": config["jobs_per_run"],
        }
        self.campaign = Campaign(campaign_config, self.executor, session_log_path(self.session_name, rq2_root))
        self._cpu_cache: dict[str, dict[str, dict[str, np.ndarray]]] = defaultdict(lambda: defaultdict(dict))
        self.report: dict[str, Any] = {"session": self.session_name}

    def _proc_stat_lines(self) -> dict[int, str]:
        lines: dict[int, str] = {}
        for line in Path("/proc/stat").read_text().splitlines():
            if line.startswith("cpu") and line[3:4].isdigit():
                lines[int(line.split()[0][3:])] = line
        return lines

    def _proc_interrupts(self) -> str:
        return Path("/proc/interrupts").read_text()

    def _monitor_loop(self, run: dict[str, Any], stop_event: threading.Event) -> None:
        interval = self.config.get("checks", {}).get("sample_interval_s", 5)
        util_high = self.config.get("checks", {}).get("utilization_high_threshold_pct", 95.0)
        util_idle = self.config.get("checks", {}).get("utilization_idle_threshold_pct", 5.0)
        rt_cores = self.config.get("platform", {}).get("rt_cores", RT_CORES_DEFAULT)
        prev_stat, prev_intr = self._proc_stat_lines(), self._proc_interrupts()
        samples = []
        while not stop_event.wait(interval):
            curr_stat, curr_intr = self._proc_stat_lines(), self._proc_interrupts()
            sample: dict[str, Any] = {"t": time.time()}
            if run.get("enemy"):
                _, cpus = run["enemy"]
                sample["enemy_busy"] = [
                    checks.check_enemy_busy(prev_stat[c], curr_stat[c], util_high).to_dict()
                    for c in cpus if c in prev_stat and c in curr_stat
                ]
            else:
                task_cpus = {inst["cpu"] for inst in run["instances"]}
                non_task = [c for c in rt_cores if c not in task_cpus and c in prev_stat and c in curr_stat]
                if non_task:
                    prev_lines = {c: prev_stat[c] for c in non_task}
                    curr_lines = {c: curr_stat[c] for c in non_task}
                    sample["baseline_idle"] = checks.check_cores_idle(prev_lines, curr_lines, util_idle).to_dict()
            sample["interrupts"] = checks.check_interrupt_load(prev_intr, curr_intr, rt_cores).to_dict()
            samples.append(sample)
            prev_stat, prev_intr = curr_stat, curr_intr
        self.report.setdefault("monitor_samples", {})[f"{run['deployment']}/{run['condition']}"] = samples

    def _post_run_checks(self, run: dict[str, Any], run_dir: Path) -> list[checks.CheckResult]:
        cfg = self.config.get("checks", {})
        workload = self.config["workload"]
        period_ns = workload["period_ms"] * 1e6

        results: list[checks.CheckResult] = []
        first_release: dict[str, int] = {}
        for inst in run["instances"]:
            rows = load_csv_rows(run_dir / f"{inst['instance_id']}.csv")
            meta = load_metadata(run_dir / f"{inst['instance_id']}.meta.json")
            exec_rows = [r for r in rows if r.get("warmup", "0") != "1"]
            first_release[inst["instance_id"]] = int(exec_rows[0]["release_ns"])

            results.append(checks.check_row_count(rows, expected_jobs=run["jobs"]))
            results.append(checks.check_no_skips(exec_rows))
            release_ns = [int(r["release_ns"]) for r in exec_rows]
            results.append(checks.check_release_spacing(release_ns, period_ns,
                                                          cfg.get("release_spacing_tol_frac", 0.02)))
            results.append(checks.check_timing_sanity(exec_rows))
            results.append(checks.check_metadata_flags(meta))
            cpu_arr = cpu_ns_array(exec_rows)
            results.append(checks.check_stalls(cpu_arr, period_ns, cfg.get("stall_factor", 2.0)))
            results.append(checks.check_stationarity(cpu_arr, cfg.get("stationarity_threshold_pct", 5.0)))
            self._cpu_cache[run["deployment"]][inst["instance_id"]][run["condition"]] = cpu_arr

        if len(run["instances"]) > 1:
            results.append(checks.check_multi_instance_alignment(first_release))

        for inst in run["instances"]:
            cache = self._cpu_cache[run["deployment"]][inst["instance_id"]]
            if run["condition"] in ("cache", "memory") and "baseline" in cache:
                results.append(checks.check_interference_effect(
                    cache["baseline"], cache[run["condition"]], cfg.get("interference_threshold", 1.02)))
            if run["condition"] == "baseline_end" and "baseline" in cache:
                results.append(checks.check_baseline_drift(
                    cache["baseline"], cache["baseline_end"], cfg.get("drift_threshold_pct", 5.0)))
        return results

    def run_managed(self, run: dict[str, Any]) -> dict[str, Any]:
        run_id = "run0"
        run_dir = raw_run_dir(self.session_name, run["deployment"], run["condition"], run_id, self.rq2_root)
        manifest_path = run_dir / "manifest.json"
        existing = read_manifest(manifest_path)
        if existing and existing.get("status") == "complete":
            self.campaign.log(f"skip (already complete): {run['deployment']}/{run['condition']}")
            return existing
        if existing and existing.get("attempt", 0) >= 2:
            self.campaign.log(f"skip (already invalid after retry): {run['deployment']}/{run['condition']}")
            return existing

        attempt = existing.get("attempt", 0) + 1 if existing else 1
        manifest = self._execute_run(run, run_dir, manifest_path, attempt)
        if manifest["checks_status"] == "FAIL" and attempt == 1:
            self.campaign.log(f"retrying once: {run['deployment']}/{run['condition']}")
            manifest = self._execute_run(run, run_dir, manifest_path, attempt=2)
        return manifest

    def _execute_run(self, run: dict[str, Any], run_dir: Path, manifest_path: Path, attempt: int) -> dict[str, Any]:
        self.campaign.log(f"start: {run['deployment']}/{run['condition']} (attempt {attempt})")
        manifest = start_manifest(run, command=["session.py"])
        manifest["attempt"] = attempt
        write_manifest(manifest_path, manifest)

        handles = self.campaign.start_interference(run)
        stop_event = threading.Event()
        monitor = threading.Thread(target=self._monitor_loop, args=(run, stop_event), daemon=True)
        if not self.dry_run:
            monitor.start()
        try:
            self.campaign.deploy_and_wait(run, run_dir, jobs=run["jobs"])
        finally:
            stop_event.set()
            if not self.dry_run:
                monitor.join(timeout=5)
            self.campaign.stop_interference(handles)

        run_checks = [] if self.dry_run else self._post_run_checks(run, run_dir)
        if self.dry_run or not run_checks:
            checks_status = "SKIPPED"
        elif all(c.status != "FAIL" for c in run_checks):
            checks_status = "PASS"
        else:
            checks_status = "FAIL"
        manifest["checks"] = [c.to_dict() for c in run_checks]
        manifest["checks_status"] = checks_status
        status = "complete" if checks_status != "FAIL" else "invalid"
        write_manifest(manifest_path, finish_manifest(manifest, status=status))
        self.campaign.log(f"{status}: {run['deployment']}/{run['condition']}")
        return manifest

    def run(self) -> dict[str, Any]:
        self.campaign.log(f"session {self.session_name}: preflight")
        preflight = run_preflight(self.rq2_root, self.config, self.dry_run)
        self.report["preflight"] = [c.to_dict() for c in preflight]
        if any(c.status == "FAIL" for c in preflight):
            self.campaign.log("preflight FAILED, aborting session")
            self.report["aborted"] = True
            self._write_report()
            raise SystemExit(1)

        platform_start = capture_platform_info(self.rq2_root, self.session_dir / "platform_info_start.json",
                                                 self.dry_run)
        self.report["platform_start"] = platform_start

        self.report["enemy_effectiveness"] = run_enemy_effectiveness(
            self.rq2_root, self.config, self.session_dir, self.dry_run)

        runs = build_session_runs(self.config)
        self.campaign.log(f"session {self.session_name}: {len(runs)} runs planned")
        pause_s = self.config.get("pause_between_runs_s", 60)
        run_reports = []
        for i, run in enumerate(runs):
            run_reports.append(self.run_managed(run))
            if i < len(runs) - 1:
                if self.dry_run:
                    self.campaign.log(f"[dry-run] would pause {pause_s}s")
                else:
                    self.campaign.log(f"pausing {pause_s}s before next run")
                    time.sleep(pause_s)
        self.report["runs"] = run_reports

        platform_end = capture_platform_info(self.rq2_root, self.session_dir / "platform_info_end.json",
                                              self.dry_run)
        self.report["platform_end"] = platform_end
        if platform_start and platform_end:
            changed = (_vm_id(platform_start) != _vm_id(platform_end) or
                       platform_start.get("cpu_model") != platform_end.get("cpu_model"))
            self.report["platform_stable"] = not changed
            if changed:
                self.campaign.log("FAIL: platform changed during session (vmId or CPU model)")

        self._write_report()
        self.campaign.log(f"session {self.session_name}: done")
        return self.report

    def _write_report(self) -> None:
        if self.dry_run:
            print("[dry-run] would write session_report.json / session_report.md")
            return
        self.session_dir.mkdir(parents=True, exist_ok=True)
        (self.session_dir / "session_report.json").write_text(json.dumps(self.report, indent=2, default=str))
        (self.session_dir / "session_report.md").write_text(render_report_md(self.report))


def render_report_md(report: dict[str, Any]) -> str:
    lines = [f"# Session report: {report['session']}", ""]
    if report.get("aborted"):
        lines.append("**SESSION ABORTED at preflight.**\n")

    def section(title: str, results: list[dict[str, Any]]) -> None:
        lines.append(f"## {title}")
        for r in results:
            lines.append(f"- **{r['status']}** `{r['name']}` - {r['detail']}")
        lines.append("")

    section("Preflight", report.get("preflight", []))
    if report.get("enemy_effectiveness"):
        lines.append("## Enemy effectiveness")
        for cond in ("cache_enemy", "memory_enemy"):
            e = report["enemy_effectiveness"].get(cond, {})
            if e:
                lines.append(f"- **{e.get('status', '?')}** {cond}: slowdown p90 = {e.get('slowdown_p90', float('nan')):.3f}")
        lines.append("")

    for run in report.get("runs", []):
        run_name = f"{run['config']['deployment']}/{run['config']['condition']}"
        lines.append(f"## Run: {run_name} (status={run.get('status')}, checks={run.get('checks_status')})")
        for c in run.get("checks", []):
            lines.append(f"- **{c['status']}** `{c['name']}` - {c['detail']}")
        lines.append("")

    if "platform_stable" in report:
        lines.append(f"## Platform stability\n- **{'PASS' if report['platform_stable'] else 'FAIL'}** "
                      f"vmId/CPU model unchanged across the session\n")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Run an unattended profiling session")
    p.add_argument("session_yaml", type=Path)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    rq2_root = find_rq2_root()
    config = load_session_config(args.session_yaml)
    Session(config, rq2_root, args.dry_run).run()


if __name__ == "__main__":
    main()
