#!/usr/bin/env python3
"""
Parse an rt-app per-loop log into a per-job CSV.

rt-app writes one log per thread: <logdir>/<log_basename>-<task>-<idx>.log with
a commented header row naming the columns. We auto-map the header (rt-app
versions differ) and emit the canonical Model 1 per-job schema:

  job_index, release_us, start_us, finish_us, C_us, R_us, slack_us,
  deadline_miss, tardiness_us

Definitions (implicit deadline = period = P; rt-app columns:
idx perf run period start end rel_st slack c_duration c_period wu_lat):
  release_us   = activation                 = 'start' (absolute activation timeline)
  start_us     = actual compute start        = start + wu_lat
  finish_us    = actual compute finish       = release + R
  C_us         = actual computation duration = 'run'   (NOT 'c_duration', which is configured)
  R_us         = response time               = deadline - slack = c_period - slack
  slack_us     = deadline - finish           = 'slack'
  deadline_miss= 1 if slack < 0 else 0
  tardiness_us = max(0, -slack)

NOTE: rt-app's 'run' is the measured compute time and 'slack' = deadline - finish,
so R = P - slack correctly grows when steal/preemption delays a job (unlike
end - start, which in this rt-app build spans the whole period).

Warm-up: the first `warmup_jobs` completed jobs are discarded (config default).
"""
from __future__ import annotations

import argparse
import csv
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import model1lib as m1  # noqa: E402

# header-name aliases -> canonical field
ALIASES = {
    "idx": "idx", "i": "idx",
    "run": "run",
    "period": "period",
    "start": "start",
    "end": "end",
    "rel_st": "rel_start", "rel_start": "rel_start",
    "slack": "slack",
    "c_duration": "c_duration", "c_dur": "c_duration", "duration": "c_duration",
    "c_period": "c_period",
    "wu_lat": "wu_lat", "wu_latency": "wu_lat", "wakeup_latency": "wu_lat",
    "perf": "perf",
}

OUT_HEADER = [
    "job_index", "release_us", "start_us", "finish_us",
    "C_us", "R_us", "slack_us", "deadline_miss", "tardiness_us",
]


def find_log(logdir: str, basename: str = "rt-app", task: str = "rt") -> str | None:
    cands = sorted(glob.glob(f"{logdir}/{basename}-{task}-*.log"))
    if not cands:
        cands = sorted(glob.glob(f"{logdir}/{basename}*.log"))
    return cands[0] if cands else None


def parse_header(line: str) -> dict:
    cols = line.lstrip("#").split()
    idx_map = {}
    for i, c in enumerate(cols):
        key = ALIASES.get(c.strip().lower())
        if key:
            idx_map[key] = i
    return idx_map


def parse_log(path: str, warmup: int):
    header = None
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                if header is None and any(a in line.lower() for a in ("run", "period", "start")):
                    header = parse_header(line)
                continue
            if header is None:
                # no header seen; assume the canonical modern rt-app order
                header = {"idx": 0, "perf": 1, "run": 2, "period": 3, "start": 4,
                          "end": 5, "rel_start": 6, "slack": 7, "c_duration": 8,
                          "c_period": 9, "wu_lat": 10}
            f = line.split()
            rows.append(f)

    def g(f, key):
        i = header.get(key)
        if i is None or i >= len(f):
            return None
        try:
            return float(f[i])
        except ValueError:
            return None

    jobs = []
    for f in rows:
        start = g(f, "start")               # absolute activation timeline (us)
        if start is None:
            continue
        run_actual = g(f, "run")            # ACTUAL compute duration = C
        c_period = g(f, "c_period")         # configured period P (= relative deadline)
        period_meas = g(f, "period")        # measured inter-activation
        slack = g(f, "slack")               # rt-app slack = deadline - finish_of_run
        wu = g(f, "wu_lat") or 0.0
        end = g(f, "end")
        idx = g(f, "idx")

        # relative deadline (P). Prefer configured c_period; fall back to measured.
        deadline_rel = c_period if c_period is not None else period_meas

        # Response time R = finish - release. rt-app gives slack = deadline - finish,
        # so R = deadline - slack. Fall back to (end - start) only if slack absent
        # (older formats where end == finish-of-compute).
        if slack is not None and deadline_rel is not None:
            R = deadline_rel - slack
        elif end is not None:
            R = end - start
        else:
            R = float("nan")

        release = start
        finish = release + R if R == R else (end if end is not None else start)
        exec_start = release + wu           # actual compute start ~ activation + wakeup
        C = run_actual if run_actual is not None else (R if R == R else float("nan"))
        miss = 1 if (slack is not None and slack == slack and slack < 0) else 0
        tard = max(0.0, -slack) if (slack is not None and slack == slack) else 0.0

        jobs.append({
            "job_index": int(idx) if idx is not None else len(jobs),
            "release_us": round(release, 3),
            "start_us": round(exec_start, 3),
            "finish_us": round(finish, 3) if finish == finish else "",
            "C_us": round(C, 3) if C == C else "",
            "R_us": round(R, 3) if R == R else "",
            "slack_us": round(slack, 3) if (slack is not None and slack == slack) else "",
            "deadline_miss": miss,
            "tardiness_us": round(tard, 3),
        })

    if warmup > 0:
        jobs = jobs[warmup:]
    return jobs


def main() -> int:
    ap = argparse.ArgumentParser(description="rt-app log -> per-job CSV")
    ap.add_argument("--logdir", required=True)
    ap.add_argument("--out", required=True, help="output jobs.csv path")
    ap.add_argument("--warmup", type=int, default=None,
                    help="jobs to discard (default: config stopping_rule.warmup_jobs)")
    ap.add_argument("--basename", default="rt-app")
    ap.add_argument("--task", default="rt")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    cfg = m1.load_config(args.config)
    warmup = args.warmup if args.warmup is not None else cfg["stopping_rule"]["warmup_jobs"]

    log = find_log(args.logdir, args.basename, args.task)
    if not log:
        sys.stderr.write(f"ERROR: no rt-app log found under {args.logdir}\n")
        return 2
    jobs = parse_log(log, warmup)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_HEADER)
        w.writeheader()
        w.writerows(jobs)
    sys.stderr.write(f"parsed {len(jobs)} jobs (after warmup={warmup}) -> {out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
