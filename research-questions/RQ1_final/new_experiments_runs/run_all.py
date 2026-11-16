#!/usr/bin/env python3
"""Runs step 0, then steps 1-5 and the figures.

    ../.venv/bin/python run_all.py                 # stops after step 0 if a validity check fails (default)
    ../.venv/bin/python run_all.py --ignore-step0  # continues anyway; the failing runs stay listed in output/step0_report.md

Environment: RQ1_RERUN_DATA (results folder), RQ1_RERUN_OUT (output folder), RQ1_EXPECTED_JOBS (default 5000; only for tests on synthetic data).
"""
import sys

import step0_validity
import step1_metrics
import step2_rounds
import step3_tests
import step4_interference
import step5_throttle
import make_figures


def main():
    rc = step0_validity.main()
    if rc != 0 and "--ignore-step0" not in sys.argv:
        print("STOP: step 0 failed; see output/step0_report.md")
        return 1
    if rc != 0:
        print("step 0 failed; continuing because --ignore-step0 was given")
    for m in (step1_metrics, step2_rounds, step3_tests, step4_interference, step5_throttle, make_figures):
        m.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
