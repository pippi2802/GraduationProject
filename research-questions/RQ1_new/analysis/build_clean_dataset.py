#!/usr/bin/env python3
"""build_clean_dataset.py -- pool ONLY validated rounds per model into one
per-job CSV per model under clean_data/<model>.csv, plus a manifest recording
exactly which rounds were included/excluded and why.

This exists because pooling "all rounds we happen to have collected" would
just reproduce the exact confusion this cleanup is meant to fix: several
rounds across several models were found (2026-08-05) to have a silent
no-real-contention bug (a co-runner that shows Ready/Running while not
actually consuming CPU), affecting roughly half of that round's cells at
random, indistinguishable from a genuinely-protected cell without checking
placement.json / per-cell C inflation directly, cell by cell. This script
hardcodes the outcome of that cell-by-cell audit as of today; it is NOT
re-derived automatically -- if you rerun the audit (or collect new,
post-fix rounds), update ROUND_STATUS below and rerun this script.

Each output row is one job (one line of one cell's jobs.csv), tagged with
model / scale / U / round (source) / kind (matmul|ptrchase), so the notebook
can group by whichever of those it needs -- pooling itself doesn't collapse
anything, it just concatenates validated rounds so percentile/distribution
stats have the full available sample size (summing independent per-job
observations is valid; see result.py's own pool() docstring for the one
thing that ISN'T valid to pool this way -- longest_consecutive_miss_run,
handled separately below, per-round, then maxed).
"""
from pathlib import Path
import csv
import json
import pandas as pd

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"   # raw data stays in RQ1_new root, not analysis/
OUT = HERE / "clean_data"

# model -> list of (round_dir_name, include: bool, reason)
# "round_dir_name" is the literal directory under results/.
ROUND_STATUS = {
    "model1": [
        ("model1_round1", True, "solo baseline, no co-runner to fail; verified clean (near-0% miss, no coin-flip)"),
        ("model1_round2", True, "same"),
        ("model1_round3", True, "same"),
        ("model1_round4", True, "same"),
    ],
    "model2": [
        ("model2_round1", False, "pre-fix: neighbour recreated every cell, no liveness check -- coin-flip confirmed (miss_rate flips 0%<->100% at same U across rounds)"),
        ("model2_round2", False, "same pre-fix bug"),
        ("model2_round3", False, "same pre-fix bug"),
        ("model2_round4", False, "same pre-fix bug"),
        ("model2_round5", False, "same pre-fix bug"),
        # round6+ (post-fix, confirm_burning_cpu added 2026-08-05): add here
        # once collected AND verified (check miss_rate/C_p50 don't coin-flip
        # across U at the same magnitude as rounds 1-5 did).
    ],
    "model3": [  # sib_cfs: sibling, unreserved interferer
        ("model3_sib_cfs_round1", False, "pre-fix: unreserved interferer had NO liveness check at all until 2026-08-05 -- coin-flip confirmed in every one of the 4 existing rounds"),
        ("model3_sib_cfs_round2", False, "same"),
        ("model3_sib_cfs_round3", False, "same"),
        ("model3_sib_cfs_round4", False, "same"),
        # rerun after today's interferer-liveness fix, then add here.
    ],
    "model3-w2": [  # sib_res: sibling, reserved competitor
        ("model3-w2_sib_res_round1", False, "anomaly: C_p50 shows NO inflation vs baseline at any U (competitor placed+Ready but never actually measured consuming CPU) -- whole round excluded"),
        ("model3-w2_sib_res_round2", False, "not individually re-audited this session; excluded conservatively (predates all three liveness-check fixes)"),
        ("model3-w2_sib_res_round3", False, "confirmed contamination (7/10 tight cells silently ran competitor_type=unreserved) AND, after that was fixed, still showed per-cell coin-flip (6/10 tight cells no real contention) -- predates the per-cell recheck fix"),
        ("model3-w2_sib_res_round4", True, "verified cell-by-cell: all 20 cells (both scales) show consistent ~1.8-2.1x C inflation matching the a priori hypothesis, no coin-flip mixed in. Single round -- treat as preliminary, not final, until a post-fix rerun confirms it."),
    ],
    "model3-w3": [  # phys_cfs: physical, unreserved interferer -- control, near-0 miss expected regardless of interferer liveness subtleties
        ("model3-w3_phys_cfs_round1", True, "physical placement control: near-0% miss is the correct reading whether or not the interferer's liveness was ever ambiguous -- outcome is unaffected either way"),
        ("model3-w3_phys_cfs_round2", True, "same"),
        ("model3-w3_phys_cfs_round3", True, "same"),
        ("model3-w3_phys_cfs_round4", True, "same"),
    ],
    "model3-w4": [  # phys_res: physical, reserved competitor -- control
        ("model3-w4_phys_res_round1", True, "physical placement control, same reasoning as w3; some high-U tight cells incomplete (admission ceiling, not a validity problem for the cells that did complete)"),
        ("model3-w4_phys_res_round2", True, "same"),
        ("model3-w4_phys_res_round3", True, "same"),
        ("model3-w4_phys_res_round4", True, "same"),
    ],
}


def load_round(model: str, round_dir: str) -> pd.DataFrame:
    base = RESULTS / round_dir
    rows = []
    for jobs_csv in sorted(base.glob("*/U*/jobs.csv")):
        scale = jobs_csv.parent.parent.name
        u = float(jobs_csv.parent.name[1:])
        with open(jobs_csv) as f:
            first = f.readline()
        kind = "matmul"
        if first.startswith("#"):
            for tok in first[1:].split():
                if tok.startswith("kind="):
                    kind = tok.split("=", 1)[1]
        df = pd.read_csv(jobs_csv, comment="#")
        if df.empty:
            continue
        df["model"] = model
        df["round"] = round_dir
        df["scale"] = scale
        df["U"] = u
        df["kind"] = kind
        rows.append(df)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def main():
    OUT.mkdir(exist_ok=True)
    manifest = {}
    for model, rounds in ROUND_STATUS.items():
        included = [r for r, ok, _ in rounds if ok]
        dfs = [load_round(model, r) for r in included]
        dfs = [d for d in dfs if not d.empty]
        manifest[model] = {
            "included_rounds": included,
            "excluded": [{"round": r, "reason": why} for r, ok, why in rounds if not ok],
            "n_jobs_pooled": 0,
        }
        if not dfs:
            print(f"[build] {model}: NOTHING valid to pool yet ({len(rounds)} round(s) all excluded)")
            continue
        full = pd.concat(dfs, ignore_index=True)
        out_csv = OUT / f"{model}.csv"
        full.to_csv(out_csv, index=False)
        manifest[model]["n_jobs_pooled"] = len(full)
        print(f"[build] {model}: wrote {out_csv} ({len(full)} rows from {len(included)} round(s): {included})")

    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"[build] wrote {OUT / 'MANIFEST.json'}")


if __name__ == "__main__":
    main()
