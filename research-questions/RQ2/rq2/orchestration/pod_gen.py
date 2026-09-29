"""Render templates/pod_template.yaml into concrete pod specs, one pod per
task instance, for a deployment (single-core: 1 instance, multi-core: 2+).

Two modes:
  profiling  - generous budget Q = factor * T (never binds), --overrun skip.
  validation - Q taken from results/derived/budget/budgets.json, --overrun continue.

Multiple instances of one deployment must release their first job at a
shared absolute CLOCK_MONOTONIC time. That clock is per-kernel (shared by
all pods on the same node, not synchronized across nodes/machines), so the
common start time is read from the WORKER NODE via NodeExecutor, never from
whatever machine happens to run pod_gen.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rq2.orchestration.node_exec import NodeExecutor

PLACEHOLDERS = ["{{NAME}}", "{{CPUS}}", "{{Q_US}}", "{{T_US}}", "{{ARGS}}", "{{RESULTS_DIR}}"]

# Margin between reading the node's clock and pods actually starting their
# periodic loop: must cover pod scheduling + container start + rt_video.py's
# own init (frame loading, mlockall, warm-up jobs).
START_AHEAD_S = 10.0
MONOTONIC_NS_CMD = ["python3", "-c", "import time; print(time.clock_gettime_ns(time.CLOCK_MONOTONIC))"]


def read_node_monotonic_ns(executor: NodeExecutor) -> int:
    if executor.dry_run:
        print("[dry-run] would read CLOCK_MONOTONIC on the worker node")
        return 0
    result = executor.run(MONOTONIC_NS_CMD, capture_output=True, text=True)
    return int(result.stdout.strip())


def compute_start_at_ns(executor: NodeExecutor, start_ahead_s: float = START_AHEAD_S) -> int:
    return read_node_monotonic_ns(executor) + int(start_ahead_s * 1_000_000_000)


def profiling_budget_us(period_ms: float, factor: float = 0.95) -> tuple[float, float]:
    t_us = period_ms * 1000.0
    return factor * t_us, t_us


def validation_budget_us(budgets_json: Path, deployment: str, instance_id: str,
                          variant: str, p: float) -> tuple[float, float]:
    """budgets.json schema: {deployment: {instance_id: {variant: {p_str: {
    "q_us": ..., "t_us": ...}}}}} - written by rq2.procedure.budget."""
    with open(budgets_json) as f:
        data = json.load(f)
    entry = data[deployment][instance_id][variant][str(p)]
    return float(entry["q_us"]), float(entry["t_us"])


def rt_video_args(instance: dict[str, Any], overrun: str, results_dir: str, start_at_ns: int) -> list[str]:
    args = [
        "-m", "rq2.workload.rt_video",
        "--instance-id", str(instance["instance_id"]),
        "--cpu", str(instance["cpu"]),
        "--period-ms", str(instance["period_ms"]),
        "--work", str(instance.get("work", 1)),
        "--width", str(instance.get("width", 1280)),
        "--height", str(instance.get("height", 720)),
        "--frames", str(instance.get("frames", 30)),
        "--overrun", overrun,
        "--start-at", str(start_at_ns),
        "--output", f"{results_dir}/{instance['instance_id']}.csv",
    ]
    if "fifo_prio" in instance:
        args += ["--fifo-prio", str(instance["fifo_prio"])]
    if instance.get("input"):
        args += ["--input", str(instance["input"])]
    if "warmup_jobs" in instance:
        args += ["--warmup-jobs", str(instance["warmup_jobs"])]
    if "jobs" in instance:
        args += ["--jobs", str(instance["jobs"])]
    elif "duration_s" in instance:
        args += ["--duration-s", str(instance["duration_s"])]
    return args


def render_pod(template: str, name: str, cpus: str, q_us: float, t_us: float,
                args: list[str], results_dir: str) -> str:
    rendered = template
    rendered = rendered.replace("{{NAME}}", name)
    rendered = rendered.replace("{{CPUS}}", str(cpus))
    rendered = rendered.replace("{{Q_US}}", str(int(round(q_us))))
    rendered = rendered.replace("{{T_US}}", str(int(round(t_us))))
    rendered = rendered.replace("{{ARGS}}", json.dumps(args))
    rendered = rendered.replace("{{RESULTS_DIR}}", results_dir)
    return rendered


def render_deployment(template: str, instances: list[dict[str, Any]], mode: str,
                       results_dir: str, executor: NodeExecutor, *,
                       factor: float = 0.95, budgets_json: Path | None = None,
                       variant: str = "full", p: float = 0.01,
                       overrun: str | None = None) -> list[str]:
    start_at_ns = compute_start_at_ns(executor)
    default_overrun = "skip" if mode == "profiling" else "continue"
    overrun = overrun or default_overrun

    pods = []
    for instance in instances:
        if mode == "profiling":
            q_us, t_us = profiling_budget_us(instance["period_ms"], factor)
        elif mode == "validation":
            if budgets_json is None:
                raise ValueError("validation mode requires budgets_json")
            q_us, t_us = validation_budget_us(budgets_json, instance.get("deployment", ""),
                                               str(instance["instance_id"]), variant, p)
        else:
            raise ValueError(f"unknown mode: {mode!r}")

        args = rt_video_args(instance, overrun, results_dir, start_at_ns)
        name = f"rq2-{mode}-{instance['instance_id']}"
        pods.append(render_pod(template, name, instance["cpu"], q_us, t_us, args, results_dir))
    return pods


def main():
    p = argparse.ArgumentParser(description="Render pod specs for a list of instances")
    p.add_argument("--template", required=True, type=Path)
    p.add_argument("--instances", required=True, type=Path, help="JSON list of instance dicts")
    p.add_argument("--mode", choices=["profiling", "validation"], required=True)
    p.add_argument("--results-dir", required=True)
    p.add_argument("--factor", type=float, default=0.95)
    p.add_argument("--budgets-json", type=Path)
    p.add_argument("--variant", default="full")
    p.add_argument("--p", type=float, default=0.01)
    p.add_argument("--overrun", choices=["skip", "continue"])
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--node-mode", choices=["local", "ssh"], default="local")
    p.add_argument("--ssh-host")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    template = args.template.read_text()
    instances = json.loads(args.instances.read_text())
    executor = NodeExecutor(mode=args.node_mode, ssh_host=args.ssh_host, dry_run=args.dry_run)

    pods = render_deployment(template, instances, args.mode, args.results_dir, executor,
                              factor=args.factor, budgets_json=args.budgets_json,
                              variant=args.variant, p=args.p, overrun=args.overrun)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for instance, pod_yaml in zip(instances, pods):
        out_path = args.output_dir / f"{instance['instance_id']}.yaml"
        out_path.write_text(pod_yaml)
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
