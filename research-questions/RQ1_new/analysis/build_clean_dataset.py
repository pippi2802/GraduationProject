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
        ("model1_ptrchase_round1", True, "solo baseline, ptrchase kind; verified clean (near-0% miss, matches matmul rounds' shape, no coin-flip) -- 2026-08-10 audit"),
        ("model1_ptrchase_round2", True, "same"),
        ("model1_ptrchase_round3", True, "same"),
        ("model1_ptrchase_round4", True, "same"),
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
        ("model3_sib_cfs_round3", False, "same"),
        # round2/round4 below are POST-FIX reruns that overwrote the old
        # pre-fix directories of the same name (see backlog 2026-08-07) --
        # NOT the same data as the "same" rows above.
        ("model3_sib_cfs_round2", True, "post-fix rerun, tight only. Placement verified correct+consistent across every cell (checked placement.json for U0.4/0.5/0.8 directly). miss_rate looks spiky at first glance (0.4%@U0.4 -> 100%@U0.5 -> 5%@U0.6 -> 0.5%@U0.7 -> 75%@U0.8) but this tracks alpha=C/Q crossing 1, not a coin-flip: C_p50 rises smoothly with U while Q shrinks per-cell headroom, so alpha crosses ~1 right around U0.5 and again hovers at ~1 at U0.8 -- exactly where H-CBS throttling makes miss rate hypersensitive to small C jitter. 2026-08-10 audit.", ),
        ("model3_sib_cfs_round4", True, "post-fix rerun, soft only, and only 2/10 U cells completed (U0.1, U0.2) -- highly partial, include what exists per the same convention as model3-w4's incomplete high-U tight cells; both completed cells verified clean (near-baseline miss rate, correct placement). 2026-08-10 audit.", ),
        # round1/round3 still only exist as the old pre-fix data (not
        # present locally to re-audit); leave excluded. Rerun+add if ever
        # collected post-fix.
        ("model3_sib_cfs_ptrchase_round1", True, "ptrchase kind, post-fix. All 4 rounds mutually consistent (no coin-flip) and near-identical to model1 baseline at every U -- essentially zero measurable SMT-sibling inflation for ptrchase under an unreserved interferer. Plausible real effect (see model3-w2_sib_res_ptrchase note) rather than a dead interferer: cross-check against the RESERVED-competitor sibling arm (model3-w2_sib_res_ptrchase) shows a small but non-zero inflation, so the interferer mechanism does register on ptrchase, just weakly. 2026-08-10 audit.", ),
        ("model3_sib_cfs_ptrchase_round2", True, "same"),
        ("model3_sib_cfs_ptrchase_round3", True, "same"),
        ("model3_sib_cfs_ptrchase_round4", True, "same"),
    ],
    "model3-w2": [  # sib_res: sibling, reserved competitor
        # UPDATED 2026-08-11: the old "model3-w2_sib_res_round1-4" directories
        # (referenced by the four entries below until today) turned out to be
        # the SAME design as "model3-w2_round1-4" (confirmed via matching
        # placement.json schema), just targeted reruns filling specific gaps
        # in the base rounds. Merged round1/round2/round3's gaps into the
        # base directories and deleted the "_sib_res_" reruns -- they no
        # longer exist on disk, so ROUND_STATUS now points at the merged,
        # complete base directories instead. All 4 rounds re-audited via the
        # alpha=C/Q crossing check (see 2026-08-10 backlog): every cell's
        # miss/no-miss outcome tracks alpha crossing 1 cleanly, no coin-flip
        # residue found in any of the four.
        ("model3-w2_round1", True, "merged 2026-08-11: base + its 1-cell gap-fill (soft/U0.4) from the old sib_res_round1 rerun. Verified clean via alpha-crossing check."),
        ("model3-w2_round2", True, "merged 2026-08-11: base soft cells + a full tight-scale redo (old sib_res_round2 rerun, per explicit choice to use the newer tight collection wholesale). Verified clean via alpha-crossing check -- the earlier flat 100% miss from U0.4-0.94 tight is explained (alpha 1.29-1.57 throughout that range, saturated throttling, not a stuck/broken run)."),
        ("model3-w2_round3", True, "merged 2026-08-11: base + its 1-cell gap-fill (soft/U0.2) from the old sib_res_round3 rerun. Verified clean via alpha-crossing check."),
        ("model3-w2_round4", True, "left untouched 2026-08-11 (its own sib_res_round4 rerun didn't match this round's actual gap, discarded rather than merged) -- already complete 20/20 as base data."),
        ("model3-w2_sib_res_ptrchase_round1", True, "ptrchase kind, post-fix. Cross-round comparison (all 4 rounds) shows consistent C_p50 and miss_rate at every U -- no coin-flip. Inflation vs model1 baseline is MUCH smaller than matmul's ~1.8-2.1x (roughly 1.0-1.1x) -- plausible real effect (ptrchase is memory-latency-bound, SMT hides its stalls far better than a compute-bound sibling), not a liveness bug: C is clearly non-zero-inflated, just mildly so. 2026-08-10 audit.", ),
        ("model3-w2_sib_res_ptrchase_round2", True, "same"),
        ("model3-w2_sib_res_ptrchase_round3", True, "same"),
        ("model3-w2_sib_res_ptrchase_round4", True, "same; note U0.1/tight shows 90% miss and U0.4/soft shows 3.4% miss -- both track alpha=C/Q crossing ~1 at those specific cells (small Q at low U leaves little headroom), same mechanism as model3_sib_cfs_round2, not an anomaly."),
    ],
    "model3-w3": [  # phys_cfs: physical, unreserved interferer -- control, near-0 miss expected regardless of interferer liveness subtleties
        ("model3-w3_phys_cfs_round1", True, "physical placement control: near-0% miss is the correct reading whether or not the interferer's liveness was ever ambiguous -- outcome is unaffected either way"),
        ("model3-w3_phys_cfs_round2", True, "same"),
        ("model3-w3_phys_cfs_round3", True, "same"),
        ("model3-w3_phys_cfs_round4", True, "same"),
        ("model3-w3_phys_cfs_ptrchase_round1", True, "ptrchase kind, physical placement control -- same reasoning as matmul control rounds, verified near-0% miss and consistent C_p50 across all 4 rounds. 2026-08-10 audit."),
        ("model3-w3_phys_cfs_ptrchase_round2", True, "same"),
        ("model3-w3_phys_cfs_ptrchase_round3", True, "same"),
        ("model3-w3_phys_cfs_ptrchase_round4", True, "same"),
    ],
    "model3-w4": [  # phys_res: physical, reserved competitor -- control
        ("model3-w4_phys_res_round1", True, "physical placement control, same reasoning as w3; some high-U tight cells incomplete (admission ceiling, not a validity problem for the cells that did complete)"),
        ("model3-w4_phys_res_round2", True, "same"),
        ("model3-w4_phys_res_round3", True, "same"),
        ("model3-w4_phys_res_round4", True, "same"),
        ("model3-w4_phys_res_ptrchase_round1", True, "ptrchase kind, physical placement control -- same reasoning as matmul control rounds, verified near-0% miss and consistent C_p50 across all 4 rounds. 2026-08-10 audit."),
        ("model3-w4_phys_res_ptrchase_round2", True, "same"),
        ("model3-w4_phys_res_ptrchase_round3", True, "same"),
        ("model3-w4_phys_res_ptrchase_round4", True, "same"),
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
