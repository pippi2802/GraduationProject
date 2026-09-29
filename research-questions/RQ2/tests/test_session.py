from rq2.orchestration import session as session_mod

MINIMAL_CONFIG = {
    "session": "test_session_profiling",
    "workload": {"period_ms": 33.3, "work": 1, "width": 64, "height": 64, "frames": 5,
                 "warmup_jobs": 5, "overrun": "skip"},
    "jobs_per_run": 10,
    "baseline_end_jobs": 5,
    "pause_between_runs_s": 0,
    "enemy_on_cpu0": False,
    "deployments": {
        "single_core": {
            "instances": [{"instance_id": "instance0", "cpu": 1, "fifo_prio": 50}],
            "runs": [
                {"name": "baseline"},
                {"name": "cache", "enemy": {"kind": "cache", "cpus": [2, 3]}},
                {"name": "memory", "enemy": {"kind": "memory", "cpus": [2, 3]}},
                {"name": "baseline_end"},
            ],
        },
    },
    "enemy": {"binary": "stress/enemy",
              "cache": {"mode": "rw", "stride_bytes": 64, "size_kb": "from_platform_llc"},
              "memory": {"mode": "rw", "stride_bytes": 64, "size_kb_multiplier": 10}},
    "enemy_effectiveness": {"enabled": False},  # avoid invoking the real bash script in unit tests
    "checks": {},
}


def _patch_paths(monkeypatch, tmp_path):
    def fake_session_raw_dir(session, rq2_root=None):
        return tmp_path / "results" / "raw" / session

    def fake_raw_run_dir(session, deployment, condition, run_id, rq2_root=None):
        return fake_session_raw_dir(session) / deployment / condition / run_id

    def fake_session_log_path(session, rq2_root=None):
        return fake_session_raw_dir(session) / "session.log"

    monkeypatch.setattr(session_mod, "session_raw_dir", fake_session_raw_dir)
    monkeypatch.setattr(session_mod, "raw_run_dir", fake_raw_run_dir)
    monkeypatch.setattr(session_mod, "session_log_path", fake_session_log_path)
    return fake_session_raw_dir, fake_raw_run_dir


def test_build_session_runs_order_and_job_counts():
    runs = session_mod.build_session_runs(MINIMAL_CONFIG)
    assert [r["condition"] for r in runs] == ["baseline", "cache", "memory", "baseline_end"]
    assert runs[0]["jobs"] == 10
    assert runs[-1]["jobs"] == 5
    assert runs[1]["enemy"] == ("cache", [2, 3])
    assert runs[0]["enemy"] is None


def test_enemy_on_cpu0_extends_enemy_cpus():
    config = dict(MINIMAL_CONFIG, enemy_on_cpu0=True)
    runs = session_mod.build_session_runs(config)
    cache_run = next(r for r in runs if r["condition"] == "cache")
    assert cache_run["enemy"] == ("cache", [2, 3, 0])


def test_session_dry_run_prints_ordered_actions_single_core(tmp_path, monkeypatch, capsys):
    _patch_paths(monkeypatch, tmp_path)
    rq2_root = session_mod.find_rq2_root()
    session = session_mod.Session(MINIMAL_CONFIG, rq2_root, dry_run=True)
    session.run()
    out = capsys.readouterr().out

    assert "preflight" in out
    assert "[dry-run] kubectl apply -f" in out
    assert "[dry-run] kubectl wait" in out
    assert "[dry-run] kubectl delete" in out
    assert "[dry-run, background]" in out  # enemy start, cache/memory runs
    assert out.index("baseline") < out.index("cache") < out.index("memory") < out.index("baseline_end")


def test_session_dry_run_prints_ordered_actions_multi_core(tmp_path, monkeypatch, capsys):
    config = dict(MINIMAL_CONFIG)
    config["deployments"] = {
        "multi_core": {
            "instances": [
                {"instance_id": "instance0", "cpu": 1, "fifo_prio": 50},
                {"instance_id": "instance1", "cpu": 2, "fifo_prio": 50},
            ],
            "runs": [
                {"name": "baseline"},
                {"name": "cache", "enemy": {"kind": "cache", "cpus": [3]}},
                {"name": "memory", "enemy": {"kind": "memory", "cpus": [3]}},
                {"name": "baseline_end"},
            ],
        },
    }
    _patch_paths(monkeypatch, tmp_path)
    rq2_root = session_mod.find_rq2_root()
    session = session_mod.Session(config, rq2_root, dry_run=True)
    session.run()
    out = capsys.readouterr().out

    # two instances -> two apply/wait/delete cycles per run
    assert out.count("[dry-run] kubectl apply -f") == 2 * 4
    assert out.count("[dry-run] kubectl delete") == 2 * 4


def test_session_dry_run_resume_skips_completed_run(tmp_path, monkeypatch, capsys):
    _patch_paths(monkeypatch, tmp_path)
    rq2_root = session_mod.find_rq2_root()
    session = session_mod.Session(MINIMAL_CONFIG, rq2_root, dry_run=True)
    baseline_run = session_mod.build_session_runs(MINIMAL_CONFIG)[0]

    session.run_managed(baseline_run)
    capsys.readouterr()

    session.run_managed(baseline_run)
    out = capsys.readouterr().out
    assert "skip (already complete)" in out
    assert "kubectl apply" not in out
