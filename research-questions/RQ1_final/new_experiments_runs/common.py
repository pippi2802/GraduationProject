"""Shared definitions and loading for the RQ1 rerun analysis (4 rounds). Read-only on the data.

Data: ../os-experiments/test-results/results/<config>_round<N>/<scale>/U<u>/jobs.csv (override with RQ1_RERUN_DATA).
Outputs: ./output (override with RQ1_RERUN_OUT). Only the rerun data is used; nothing from the earlier (frozen) campaign.
"""
import os
import pathlib

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
DATA = pathlib.Path(os.environ.get("RQ1_RERUN_DATA", HERE.parent / "os-experiments" / "test-results" / "results"))
OUT = pathlib.Path(os.environ.get("RQ1_RERUN_OUT", HERE / "output"))
EXPECTED_JOBS = int(os.environ.get("RQ1_EXPECTED_JOBS", "5000"))

ROUNDS = [1, 2, 3, 4]
FULL = "full isolation"
# (scenario code, name in tables, label in figures); the order is the row order of the existing figures (08 before 06).
# 07 (every lever reverted) is new in the rerun; it is appended last.
LEVERS = [("01", "isolcpus removed", "isolcpus reverted"),
          ("02", "nohz_full removed", "nohz_full reverted"),
          ("03", "rcu_nocbs removed", "rcu_nocbs reverted"),
          ("04", "systemd containment removed", "systemd containment reverted"),
          ("05", "IRQ steering removed", "IRQ steering reverted"),
          ("08", "frequency pinning removed", "frequency pinning reverted"),
          ("06", "boot-params bundle removed", "boot-params bundle reverted"),
          ("07", "all defaults", "all defaults")]
CONFIGS = [FULL] + [n for _, n, _ in LEVERS]
FREQ = "frequency pinning removed"
CODE = {n: c for c, n, _ in LEVERS}
FIG_LABEL = {FULL: "full isolation", **{n: l for _, n, l in LEVERS}}
NOT_RUN_CONFIGS = {"isolcpus removed", "all defaults"}          # U = 0.94 was not run without isolcpus

# (name, slug, title, model of the lever runs, folder of the full-isolation runs)
PLACEMENTS = [("single-core", "singlecore", "Single-core", "model1", "model1"),
              ("multi-core", "multicore", "Multi-core", "model5", "model5-phys")]
PLACE_NAMES = [p[0] for p in PLACEMENTS]
_PLACE = {p[0]: p for p in PLACEMENTS}
SCALES = [("tight", 10_000, "Tight, $P = 10$ ms"), ("soft", 100_000, "Soft, $P = 100$ ms")]     # column groups, left to right
PERIOD = {s: p for s, p, _ in SCALES}
UTILS = [0.1, 0.5, 0.7, 0.94]
K_WINDOW = 100
HEADROOM = 0.7                       # calibration target: median C = 0.7 * Q for full isolation
INTERRUPT_US = 10.0                  # a job is interrupted when mid_job_preempt_us > 10 us
THROTTLE_TOL = 0.10                  # step 5: within 10% of (P - Q)
N_PERM = 100_000
SEED = 20261104                      # same seed as the earlier significance test (rq1_significance)

COLS = ["job_index", "release_us", "start_us", "finish_us", "C_cputime_us", "R_wall_us",
        "dispatch_latency_us", "mid_job_preempt_us", "deadline_miss", "nonvol_ctxt", "skipped_before"]


def planned(config, u):
    """False for the cells that were not run (U = 0.94 without isolcpus)"""
    return not (config in NOT_RUN_CONFIGS and u == 0.94)


def cells():
    """all planned cells (placement, config, scale, U), in the fixed order"""
    return [(pl, c, s, u) for pl in PLACE_NAMES for c in CONFIGS for s, _, _ in SCALES for u in UTILS if planned(c, u)]


def run_path(placement, config, scale, u, rnd):
    _, _, _, model, base = _PLACE[placement]
    name = base if config == FULL else f"{CODE[config]}-{model}"
    return DATA / f"{name}_round{rnd}" / scale / f"U{u:g}" / "jobs.csv"


def load_run(path):
    df = pd.read_csv(path, comment="#", usecols=COLS)
    return {c: df[c].to_numpy() for c in COLS}


_CACHE = {}


def get_runs():
    """{(placement, config, scale, U, round): dict of numpy arrays} for every planned run whose file exists; plus the list of missing runs"""
    if "runs" not in _CACHE:
        runs, missing = {}, []
        for pl, c, s, u in cells():
            for r in ROUNDS:
                p = run_path(pl, c, s, u, r)
                if p.is_file():
                    runs[(pl, c, s, u, r)] = load_run(p)
                else:
                    missing.append((pl, c, s, u, r))
        _CACHE["runs"], _CACHE["missing"] = runs, missing
    return _CACHE["runs"], _CACHE["missing"]


# ---------------------------------------------------------------- release sequence
def skips_after_job(release_us, period_us):
    """releases skipped right after each job, from gaps in release_us: a gap of ~2P is 1 skip, ~3P is 2 skips, ...
    Skipped releases have no row. The last job has no following release in the file, so its skips cannot be seen from gaps (0)."""
    gap = np.diff(release_us)
    s = np.clip(np.rint(gap / period_us).astype(np.int64) - 1, 0, None)
    return np.r_[s, 0]


def lost_sequence(a, period_us):
    """0/1 array over all releases of the run (a job, then the releases skipped after it); 1 = lost (deadline miss or skipped), and the number of skipped releases"""
    n = len(a["release_us"])
    s = skips_after_job(a["release_us"], period_us)
    seq = np.ones(n + int(s.sum()), dtype=np.int8)
    pos = np.arange(n) + np.r_[0, np.cumsum(s)[:-1]]
    seq[pos] = a["deadline_miss"].astype(np.int8)
    return seq, int(s.sum())


def worst_window_lost(seq, k=K_WINDOW):
    if len(seq) < k:
        return int(seq.sum())
    cs = np.r_[0, np.cumsum(seq, dtype=np.int64)]
    return int((cs[k:] - cs[:-k]).max())


def longest_run(seq):
    if not seq.any():
        return 0
    d = np.diff(np.r_[0, seq, 0])
    return int((np.flatnonzero(d == -1) - np.flatnonzero(d == 1)).max())


# ---------------------------------------------------------------- statistics helpers
def holm(p):
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for i, idx in enumerate(order):
        run = max(run, (m - i) * p[idx])
        adj[idx] = min(1.0, run)
    return adj


# ---------------------------------------------------------------- LaTeX
def tex_name(s):
    return s.replace("_", r"\_")


def grid_tex(configs, get, caption, label, small=False, extra_rows=None):
    """booktabs table in the style of the existing RQ1 tables: one row per configuration, columns = tight U's | soft U's.
    get(config, scale, U) -> string"""
    ncol = len(SCALES) * len(UTILS)
    lines = [r"\begin{table}[ht]", r"\centering", r"\small" if not small else r"\scriptsize", r"\resizebox{\textwidth}{!}{%",
             r"\begin{tabular}{l|" + "|".join(["r" * len(UTILS)] * len(SCALES)) + "}", r"\toprule",
             " & " + " & ".join(rf"\multicolumn{{{len(UTILS)}}}{{c}}{{{title}}}" for _, _, title in SCALES) + r" \\",
             "Configuration & " + " & ".join(f"{u:g}" for _ in SCALES for u in UTILS) + r" \\", r"\midrule"]
    for i, c in enumerate(configs):
        if i == 1:
            lines.append(rf"\cmidrule{{1-{1 + ncol}}}")
        lines.append(f"{tex_name(c)} & " + " & ".join(get(c, s, u) for s, _, _ in SCALES for u in UTILS) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}}", r"\caption{" + caption + "}", r"\label{" + label + "}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def fnum(x, nd=2, nr=False):
    if nr:
        return "n/r"
    return "--" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"
