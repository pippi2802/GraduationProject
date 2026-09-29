import json

from rq2.orchestration import pod_gen
from rq2.orchestration.node_exec import NodeExecutor

DUMMY_TEMPLATE = """\
name: {{NAME}}
cpus: {{CPUS}}
q_us: {{Q_US}}
t_us: {{T_US}}
args: {{ARGS}}
results_dir: {{RESULTS_DIR}}
"""


def test_render_pod_substitutes_all_placeholders():
    out = pod_gen.render_pod(DUMMY_TEMPLATE, "n0", "1", 1000.0, 2000.0, ["--foo", "bar"], "/results/r0")
    for placeholder in pod_gen.PLACEHOLDERS:
        assert placeholder not in out
    assert "name: n0" in out
    assert "cpus: 1" in out
    assert "q_us: 1000" in out
    assert "t_us: 2000" in out
    assert "results_dir: /results/r0" in out
    args_line = [line for line in out.splitlines() if line.startswith("args:")][0]
    assert json.loads(args_line.split("args:", 1)[1].strip()) == ["--foo", "bar"]


def test_profiling_budget_is_a_fraction_of_period():
    q_us, t_us = pod_gen.profiling_budget_us(period_ms=33.3, factor=0.95)
    assert t_us == 33300.0
    assert q_us == 33300.0 * 0.95


def test_render_deployment_profiling_dry_run(capsys):
    instances = [
        {"instance_id": "instance0", "cpu": 1, "period_ms": 33.3, "work": 3, "jobs": 100},
    ]
    executor = NodeExecutor(dry_run=True)
    pods = pod_gen.render_deployment(DUMMY_TEMPLATE, instances, "profiling", "/results/r0", executor)
    assert len(pods) == 1
    assert "name: rq2-profiling-instance0" in pods[0]
    # profiling never binds the budget: q_us should equal factor * t_us
    assert "q_us: 31635" in pods[0]  # 0.95 * 33300, rounded
    args_line = [line for line in pods[0].splitlines() if line.startswith("args:")][0]
    args = json.loads(args_line.split("args:", 1)[1].strip())
    assert "--overrun" in args and args[args.index("--overrun") + 1] == "skip"
    captured = capsys.readouterr()
    assert "dry-run" in captured.out
