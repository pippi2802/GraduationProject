from pathlib import Path

from rq2.orchestration import campaign as campaign_mod
from rq2.orchestration.node_exec import NodeExecutor

MINIMAL_CONFIG = {
    "kind": "profiling",
    "session": "test_session",
    "workload": {"period_ms": 33.3, "work": 1, "width": 64, "height": 64, "frames": 5, "overrun": "skip"},
    "jobs_per_run": 10,
    "sessions_per_condition": 1,
    "deployments": {
        "single_core": {
            "instances": [{"instance_id": "instance0", "cpu": 1, "fifo_prio": 50}],
            "dial_levels": [],
        },
    },
    "housekeeping_load": {"enabled": False},
}


def make_campaign(tmp_path, monkeypatch):
    def fake_raw_run_dir(session, deployment, condition, run_id, rq2_root=None):
        return tmp_path / "results" / "raw" / session / deployment / condition / run_id

    monkeypatch.setattr(campaign_mod, "raw_run_dir", fake_raw_run_dir)
    executor = NodeExecutor(dry_run=True)
    return campaign_mod.Campaign(MINIMAL_CONFIG, executor, tmp_path / "campaign.log"), fake_raw_run_dir


def test_build_runs_profiling_baseline_only():
    runs = campaign_mod.build_runs(MINIMAL_CONFIG)
    assert len(runs) == 1
    assert runs[0]["condition"] == "baseline"
    assert runs[0]["deployment"] == "single_core"


def test_dry_run_only_prints_commands(tmp_path, monkeypatch, capsys):
    campaign, fake_raw_run_dir = make_campaign(tmp_path, monkeypatch)
    runs = campaign_mod.build_runs(MINIMAL_CONFIG)
    campaign.run_one(runs[0])

    captured = capsys.readouterr()
    assert "[dry-run] kubectl apply -f" in captured.out
    assert "[dry-run] kubectl wait" in captured.out
    assert "[dry-run] kubectl delete" in captured.out

    run_dir = fake_raw_run_dir("test_session", "single_core", "baseline", "session0")
    manifest_path = run_dir / "manifest.json"
    assert manifest_path.exists()
    from rq2.common.manifest import read_manifest
    manifest = read_manifest(manifest_path)
    assert manifest["status"] == "complete"


def test_resume_skips_completed_run(tmp_path, monkeypatch, capsys):
    campaign, fake_raw_run_dir = make_campaign(tmp_path, monkeypatch)
    runs = campaign_mod.build_runs(MINIMAL_CONFIG)

    campaign.run_one(runs[0])
    capsys.readouterr()  # discard first-run output

    campaign.run_one(runs[0])
    captured = capsys.readouterr()
    assert "skip (already complete)" in captured.out
    assert "kubectl apply" not in captured.out
