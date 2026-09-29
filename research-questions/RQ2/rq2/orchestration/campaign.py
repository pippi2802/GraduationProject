"""Drive a profiling or validation campaign from a YAML config: for each run,
start interference -> deploy pod(s) -> wait -> collect results -> manifest ->
stop interference -> delete pod. Resumable: a run whose manifest already
says "complete" is skipped. Never touches kubectl/ssh for real unless
--dry-run is explicitly omitted; tests always pass --dry-run.
"""
from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Iterator

import yaml

from rq2.common.manifest import finish_manifest, is_complete, start_manifest, write_manifest
from rq2.common.paths import campaign_log_path, find_rq2_root, raw_run_dir
from rq2.orchestration.node_exec import NodeExecutor
from rq2.orchestration import pod_gen


def load_campaign(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def run_id_for(session_idx: int) -> str:
    return f"session{session_idx}"


def build_runs_profiling(config: dict[str, Any]) -> Iterator[dict[str, Any]]:
    n_sessions = config["sessions_per_condition"]
    for deployment, dep_cfg in config["deployments"].items():
        conditions: list[dict[str, Any]] = [{"name": "baseline", "enemy": None}]
        for dial in dep_cfg["dial_levels"]:
            conditions.append({"name": f"cache_enemy_{dial['name']}", "enemy": ("cache", dial["enemy_cpus"])})
            conditions.append({"name": f"memory_enemy_{dial['name']}", "enemy": ("memory", dial["enemy_cpus"])})
        if config.get("housekeeping_load", {}).get("enabled"):
            conditions.append({"name": "hk_loaded", "hk_load": True})

        for condition, session_idx in itertools.product(conditions, range(n_sessions)):
            yield {
                "deployment": deployment,
                "instances": dep_cfg["instances"],
                "condition": condition["name"],
                "enemy": condition.get("enemy"),
                "hk_load": condition.get("hk_load", False),
                "session_idx": session_idx,
                "mode": "profiling",
            }


def build_runs_validation(config: dict[str, Any]) -> Iterator[dict[str, Any]]:
    n_sessions = config["sessions_per_condition"]
    for deployment, dep_cfg in config["deployments"].items():
        for variant, p, stress in itertools.product(config["variants"], config["p_levels"], config["stress"]):
            condition = f"{variant}_p{p}_stress-{stress}"
            enemy_cpus = dep_cfg["stress_enemy_cpus"] if stress == "on" else None
            for session_idx in range(n_sessions):
                yield {
                    "deployment": deployment,
                    "instances": dep_cfg["instances"],
                    "condition": condition,
                    "enemy": ("cache", enemy_cpus) if enemy_cpus else None,
                    "hk_load": False,
                    "session_idx": session_idx,
                    "mode": "validation",
                    "variant": variant,
                    "p": p,
                }


def build_runs(config: dict[str, Any]) -> list[dict[str, Any]]:
    if config["kind"] == "profiling":
        return list(build_runs_profiling(config))
    if config["kind"] == "validation":
        return list(build_runs_validation(config))
    raise ValueError(f"unknown campaign kind: {config['kind']!r}")


def enemy_binary_and_args(config: dict[str, Any], kind: str, cpu: int) -> list[str]:
    rq2_root = find_rq2_root()
    binary = str(rq2_root / config["enemy"]["binary"])
    preset = config["enemy"][kind]
    if kind == "cache":
        size_kb = preset["size_kb"]
        if size_kb == "from_platform_llc":
            with open(rq2_root / "configs" / "platform.yaml") as f:
                size_kb = yaml.safe_load(f)["llc_size_kb"]
    else:
        llc_kb = None
        with open(rq2_root / "configs" / "platform.yaml") as f:
            llc_kb = yaml.safe_load(f)["llc_size_kb"]
        size_kb = (llc_kb or 0) * preset.get("size_kb_multiplier", 10)
    return [binary, "--size-kb", str(size_kb), "--stride-bytes", str(preset["stride_bytes"]),
            "--mode", preset["mode"], "--cpu", str(cpu)]


class Campaign:
    def __init__(self, config: dict[str, Any], executor: NodeExecutor, log_path: Path):
        self.config = config
        self.executor = executor
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, msg: str) -> None:
        line = f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {msg}"
        print(line)
        if not self.executor.dry_run:
            with open(self.log_path, "a") as f:
                f.write(line + "\n")

    def start_interference(self, run: dict[str, Any]) -> list[Any]:
        handles: list[Any] = []
        if run.get("enemy"):
            kind, cpus = run["enemy"]
            for cpu in cpus:
                cmd = enemy_binary_and_args(self.config, kind, cpu)
                self.log(f"start enemy: {' '.join(cmd)}")
                handles.append(("enemy", self.executor.run_background(cmd)))
        if run.get("hk_load"):
            rq2_root = find_rq2_root()
            hk_cpu = self.config["housekeeping_load"]["cpu"]
            pidfile = f"/tmp/rq2_hk_load_{run['deployment']}_{run['condition']}.pid"
            cmd = [str(rq2_root / "stress" / "hk_load.sh"), "start", "--cpu", str(hk_cpu), "--pidfile", pidfile]
            self.log(f"start hk_load: {' '.join(cmd)}")
            self.executor.run(cmd)
            handles.append(("hk_load", pidfile))
        return handles

    def stop_interference(self, handles: list[Any]) -> None:
        rq2_root = find_rq2_root()
        for kind, handle in handles:
            if kind == "enemy":
                self.log("stop enemy (SIGTERM)")
                if handle is not None:
                    handle.terminate()
            elif kind == "hk_load":
                cmd = [str(rq2_root / "stress" / "hk_load.sh"), "stop", "--pidfile", handle]
                self.log(f"stop hk_load: {' '.join(cmd)}")
                self.executor.run(cmd)

    def deploy_and_wait(self, run: dict[str, Any], run_dir: Path, jobs: int | None = None) -> None:
        rq2_root = find_rq2_root()
        workload = self.config["workload"]
        jobs = jobs if jobs is not None else self.config["jobs_per_run"]
        extra = {"period_ms": workload["period_ms"], "work": workload.get("work", 1),
                 "width": workload.get("width", 1280), "height": workload.get("height", 720),
                 "frames": workload.get("frames", 30), "jobs": jobs}
        if workload.get("input"):
            extra["input"] = workload["input"]
        if workload.get("warmup_jobs") is not None:
            extra["warmup_jobs"] = workload["warmup_jobs"]
        instances = [dict(inst, deployment=run["deployment"], **extra) for inst in run["instances"]]
        template = (rq2_root / "templates" / "pod_template.yaml").read_text()
        overrun = self.config["workload"].get("overrun")
        budgets_json = rq2_root / self.config.get("budget_json", "results/derived/budget/budgets.json")

        pods = pod_gen.render_deployment(
            template, instances, run["mode"], str(run_dir), self.executor,
            budgets_json=budgets_json if run["mode"] == "validation" else None,
            variant=run.get("variant", "full"), p=run.get("p", 0.01), overrun=overrun,
        )
        pod_paths = []
        for inst, pod_yaml in zip(instances, pods):
            pod_path = run_dir / f"pod_{inst['instance_id']}.yaml"
            if not self.executor.dry_run:
                run_dir.mkdir(parents=True, exist_ok=True)
                pod_path.write_text(pod_yaml)
            pod_paths.append(pod_path)
            self.executor.run(["kubectl", "apply", "-f", str(pod_path)])
            self.log(f"deployed pod for {inst['instance_id']}")

        for inst, pod_path in zip(instances, pod_paths):
            name = f"rq2-{run['mode']}-{inst['instance_id']}"
            self.executor.run(["kubectl", "wait", "--for=condition=Ready", f"pod/{name}", "--timeout=600s"])
            self.executor.run(["kubectl", "wait", "--for=jsonpath={.status.phase}=Succeeded",
                                f"pod/{name}", "--timeout=3600s"])
            self.log(f"pod {name} finished")

        for inst, pod_path in zip(instances, pod_paths):
            name = f"rq2-{run['mode']}-{inst['instance_id']}"
            self.executor.run(["kubectl", "delete", "pod", name, "--ignore-not-found"])

    def run_one(self, run: dict[str, Any]) -> None:
        run_id = run_id_for(run["session_idx"])
        run_dir = raw_run_dir(self.config["session"], run["deployment"], run["condition"], run_id)
        manifest_path = run_dir / "manifest.json"

        if is_complete(manifest_path):
            self.log(f"skip (already complete): {run['deployment']}/{run['condition']}/{run_id}")
            return

        self.log(f"start: {run['deployment']}/{run['condition']}/{run_id}")
        manifest = start_manifest(run, command=["campaign.py"])
        write_manifest(manifest_path, manifest)

        handles = self.start_interference(run)
        try:
            self.deploy_and_wait(run, run_dir)
        finally:
            self.stop_interference(handles)

        write_manifest(manifest_path, finish_manifest(manifest))
        self.log(f"complete: {run['deployment']}/{run['condition']}/{run_id}")


def main():
    p = argparse.ArgumentParser(description="Run a profiling or validation campaign from YAML")
    p.add_argument("campaign_yaml", type=Path)
    p.add_argument("--node-mode", choices=["local", "ssh"], default="local")
    p.add_argument("--ssh-host")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    config = load_campaign(args.campaign_yaml)
    executor = NodeExecutor(mode=args.node_mode, ssh_host=args.ssh_host, dry_run=args.dry_run)
    log_path = campaign_log_path(config["session"])

    campaign = Campaign(config, executor, log_path)
    runs = build_runs(config)
    campaign.log(f"campaign {config['session']}: {len(runs)} runs planned")
    for run in runs:
        campaign.run_one(run)


if __name__ == "__main__":
    main()
