import shutil
import subprocess
from pathlib import Path

import pytest

RQ2_ROOT = Path(__file__).resolve().parent.parent
STRESS_DIR = RQ2_ROOT / "stress"
VICTIM_BIN = STRESS_DIR / "victim"


@pytest.fixture(scope="module", autouse=True)
def built_victim():
    if shutil.which("cc") is None and shutil.which("gcc") is None:
        pytest.skip("no C compiler available")
    subprocess.run(["make", "-C", str(STRESS_DIR)], check=True)
    assert VICTIM_BIN.exists()
    yield
    subprocess.run(["make", "-C", str(STRESS_DIR), "clean"], check=True)


def test_victim_rejects_missing_args():
    result = subprocess.run([str(VICTIM_BIN)], capture_output=True, text=True)
    assert result.returncode != 0


def test_victim_prints_a_single_elapsed_ms_number():
    result = subprocess.run(
        [str(VICTIM_BIN), "--size-kb", "64", "--stride-bytes", "64", "--passes", "5"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    assert len(lines) == 1
    elapsed_ms = float(lines[0])
    assert elapsed_ms >= 0.0


def test_victim_does_fixed_work_and_finishes_quickly():
    # a short, fixed amount of work should complete well within the test's
    # own timeout without needing to be killed - proves it's not looping
    # forever like enemy.c is meant to.
    result = subprocess.run(
        [str(VICTIM_BIN), "--size-kb", "256", "--stride-bytes", "64", "--passes", "10", "--cpu", "0"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
