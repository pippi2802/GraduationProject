import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

RQ2_ROOT = Path(__file__).resolve().parent.parent
STRESS_DIR = RQ2_ROOT / "stress"
ENEMY_BIN = STRESS_DIR / "enemy"


@pytest.fixture(scope="module", autouse=True)
def built_enemy():
    if shutil.which("cc") is None and shutil.which("gcc") is None:
        pytest.skip("no C compiler available")
    subprocess.run(["make", "-C", str(STRESS_DIR)], check=True)
    assert ENEMY_BIN.exists()
    yield
    subprocess.run(["make", "-C", str(STRESS_DIR), "clean"], check=True)


def test_enemy_rejects_missing_args():
    result = subprocess.run([str(ENEMY_BIN)], capture_output=True, text=True)
    assert result.returncode != 0


def test_enemy_runs_and_exits_on_sigterm():
    proc = subprocess.Popen(
        [str(ENEMY_BIN), "--size-kb", "64", "--stride-bytes", "64", "--mode", "rw"],
        stderr=subprocess.PIPE, text=True,
    )
    time.sleep(1.0)
    assert proc.poll() is None, "enemy exited early instead of looping"
    proc.send_signal(signal.SIGTERM)
    try:
        _, stderr = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("enemy did not exit within 5s of SIGTERM")
    assert proc.returncode == 0
    assert "exiting" in stderr


def test_enemy_read_mode_1s():
    proc = subprocess.Popen(
        [str(ENEMY_BIN), "--size-kb", "128", "--mode", "read"],
        stderr=subprocess.PIPE, text=True,
    )
    time.sleep(1.0)
    proc.send_signal(signal.SIGTERM)
    proc.communicate(timeout=5)
    assert proc.returncode == 0
