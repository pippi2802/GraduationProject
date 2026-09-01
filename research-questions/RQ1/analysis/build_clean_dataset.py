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
model / scale / U / round (source) / kind (matmul|primes), so the notebook
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
        # ptrchase-kind rounds removed 2026-08-14: ptrchase workload retired,
        # replaced by primes (trial-division primality, genuinely
        # data-dependent). All ptrchase result data deleted; see
        # backlog/2026-08-14.md. Primes rounds go here once collected.
        # primes kind, 2026-08-19: first 3 collection attempts hit real bugs
        # (generated_primes/ staleness baking in a pre-primes-support image;
        # then a stale K=190 baked into the manifest from before this node's
        # isolcpus/nohz_full got applied, producing C~5x the calibration
        # target) -- both root-caused and fixed, then recalibrated fresh and
        # regenerated; verified via C_cputime_us matching the new calibration
        # target before trusting the round. All 4 rounds 20/20 cells, single
        # kind=primes throughout, no short cells.
        ("model1_primes_round1", True, "post-fix, verified clean"),
        ("model1_primes_round2", True, "post-fix, verified clean"),
        ("model1_primes_round3", True, "post-fix, verified clean"),
        ("model1_primes_round4", True, "post-fix, verified clean"),
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
        # CORRECTED 2026-08-12: this whole section was wrong. The bare
        # "model3_round1-4" directories (no "_sib_cfs_" in the name) are the
        # SAME current design (confirmed via matching placement.json schema,
        # same as the model3-w2 dual-naming resolution 2026-08-11) -- not
        # legacy/pre-fix data as previously assumed here. They were simply
        # never checked because the ROUND_STATUS entries only ever
        # referenced the "_sib_cfs_" name. round1 was already complete
        # (20/20). round2 was missing exactly the 8 tight cells that
        # "model3_sib_cfs_round2" (a full tight-scale rerun) covers --
        # merged the same way as model3-w2's round2, then deleted the now-
        # redundant "_sib_cfs_round2"/"_sib_cfs_round4" directories
        # (round4's rerun was redundant with round1, never actually filled
        # round4's real gap anyway, per the 2026-08-11 investigation).
        ("model3_round1", True, "complete, 20/20 cells, verified via alpha=C/Q crossing check (2026-08-10): every cell's miss/no-miss outcome tracks alpha crossing 1 cleanly, no coin-flip residue."),
        ("model3_round2", True, "merged 2026-08-12: base soft cells (all 10) + full tight-scale redo (the old model3_sib_cfs_round2, which had already been alpha-crossing verified on 2026-08-10: miss_rate spikes at U0.5/U0.8 track alpha crossing 1, not a coin-flip, placement.json checked correct for the affected cells)."),
        ("model3_round3", True, "19/20 cells, missing only tight/U0.94 -- no rerun available to fill it. Not a validity problem for the cells that did complete, same convention as model3-w4's incomplete high-U tight cells."),
        ("model3_round4", True, "19/20 cells, missing only tight/U0.2 -- no rerun available to fill it (the old model3_sib_cfs_round4's 2 cells were soft/U0.1-0.2, redundant with round1, never actually matched this gap)."),
        # ptrchase-kind rounds removed 2026-08-14 (see model1 note above).
        # primes kind, 2026-08-16: all 4 rounds validated structurally (20/20
        # cells, 5000 rows, correct kind, no dup/non-monotonic job_index, no
        # cross-cell contamination in placement.json) and via the alpha=C/Q
        # crossing check -- 160/160 cells across model3+model3-w2 combined
        # match the outcome alpha predicts, zero exceptions. Round-to-round
        # miss_rate DOES flip between ~0% and ~100% at the same nominal U far
        # more than matmul ever showed -- this is real, not a coin-flip bug:
        # primes' intrinsic per-job cv (~0.1-0.3, data-dependent early-exit
        # trial division) is wide enough that the same U straddles alpha=1
        # differently round to round under sibling contention. See
        # backlog/2026-08-14.md and 2026-08-15/16 chat for the full audit
        # (also cross-checked against nonvol_ctxt/mid_job_preempt_us: exactly
        # 1 involuntary context switch on 98.3% of alpha>=1 jobs, duration
        # scaling with the period -- the H-CBS budget-exhaustion signature,
        # not scheduler noise).
        ("model3_sib_cfs_primes_round1", True, "validated 2026-08-16, see above"),
        ("model3_sib_cfs_primes_round2", True, "validated 2026-08-16, see above"),
        ("model3_sib_cfs_primes_round3", True, "validated 2026-08-16, see above"),
        ("model3_sib_cfs_primes_round4", True, "validated 2026-08-16, see above"),
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
        # ptrchase-kind rounds removed 2026-08-14 (see model1 note above).
        # primes kind, 2026-08-16: same validation as model3's primes rounds
        # above (structural + alpha-crossing check combined across both).
        ("model3-w2_sib_res_primes_round1", True, "validated 2026-08-16, see model3's primes note above"),
        ("model3-w2_sib_res_primes_round2", True, "validated 2026-08-16, see model3's primes note above"),
        ("model3-w2_sib_res_primes_round3", True, "validated 2026-08-16, see model3's primes note above"),
        ("model3-w2_sib_res_primes_round4", True, "validated 2026-08-16, see model3's primes note above"),
    ],
    "model3-w3": [  # phys_cfs: physical, unreserved interferer -- control, near-0 miss expected regardless of interferer liveness subtleties
        ("model3-w3_phys_cfs_round1", True, "physical placement control: near-0% miss is the correct reading whether or not the interferer's liveness was ever ambiguous -- outcome is unaffected either way"),
        ("model3-w3_phys_cfs_round2", True, "same"),
        ("model3-w3_phys_cfs_round3", True, "same"),
        ("model3-w3_phys_cfs_round4", True, "same"),
        # ptrchase-kind rounds removed 2026-08-14 (see model1 note above).
        # primes kind, 2026-08-16: validated structurally (20/20 cells each,
        # correct kind/placement). Physical-separation control: essentially
        # zero miss across all 4 rounds (mean miss_rate 0.0001, alpha_p50
        # stays 0.63-0.78 throughout) and near-zero preemption signal
        # (nonvol_ctxt=0.00, mid_job_preempt_us~1.3us mean across 400k jobs
        # pooled with w4) -- confirms the sibling-arm coin-flip behavior is
        # specifically an SMT-sharing effect, not residual system noise.
        ("model3-w3_phys_cfs_primes_round1", True, "validated 2026-08-16, see note above"),
        ("model3-w3_phys_cfs_primes_round2", True, "validated 2026-08-16, see note above"),
        ("model3-w3_phys_cfs_primes_round3", True, "validated 2026-08-16, see note above"),
        ("model3-w3_phys_cfs_primes_round4", True, "validated 2026-08-16, see note above"),
    ],
    "model3-w4": [  # phys_res: physical, reserved competitor -- control
        ("model3-w4_phys_res_round1", True, "physical placement control, same reasoning as w3; some high-U tight cells incomplete (admission ceiling, not a validity problem for the cells that did complete)"),
        ("model3-w4_phys_res_round2", True, "same"),
        ("model3-w4_phys_res_round3", True, "same"),
        ("model3-w4_phys_res_round4", True, "same"),
        # ptrchase-kind rounds removed 2026-08-14 (see model1 note above).
        # primes kind, 2026-08-16: same validation as model3-w3's primes
        # rounds above (physical-separation control, pooled preemption stats
        # computed together with w3).
        ("model3-w4_phys_res_primes_round1", True, "validated 2026-08-16, see model3-w3's primes note above"),
        ("model3-w4_phys_res_primes_round2", True, "validated 2026-08-16, see model3-w3's primes note above"),
        ("model3-w4_phys_res_primes_round3", True, "validated 2026-08-16, see model3-w3's primes note above"),
        ("model3-w4_phys_res_primes_round4", True, "validated 2026-08-16, see model3-w3's primes note above"),
    ],
    # model4 -- new 2026-08-18/19 design, periodic-vs-event-triggered
    # activation. Two separate keys (not two workload kinds under one, the
    # way model3-family splits) since periodic and event are the two arms
    # of the comparison itself, running on separate nodes/namespaces.
    # Directory naming is inconsistent (primes rounds are missing the
    # underscore before "primes", e.g. "model4-eventprimes_round1" not
    # "model4-event_primes_round1") -- cosmetic only, load_round() reads
    # kind from each jobs.csv's own header comment, not from the directory
    # name, so this doesn't affect correctness.
    "model4-periodic": [
        ("model4-periodic_round1", True, "20/20 cells, kind=matmul throughout, no short cells"),
        ("model4-periodic_round2", True, "same"),
        ("model4-periodic_round3", True, "same"),
        ("model4-periodic_round4", True, "same"),
        ("model4-periodicprimes_round1", True, "20/20 cells, kind=primes throughout, no short cells"),
        ("model4-periodicprimes_round2", True, "same"),
        ("model4-periodicprimes_round3", True, "same"),
        ("model4-periodicprimes_round4", True, "same"),
    ],
    "model4-event": [
        ("model4-event_round1", True, "20/20 cells, kind=matmul; soft/U0.2 (4934/5000) and soft/U0.4 (4986/5000) slightly short -- collected across the 2026-08-19 trigger-coalescing bugfix transition (see matmul.c generator/target fix); rounds 2-4 below confirm 5000/5000 on every cell post-fix, so this round's shortfall (<2% of two cells) is left in rather than discarded, not excluded"),
        ("model4-event_round2", True, "20/20 cells, kind=matmul, no short cells (post-fix)"),
        ("model4-event_round3", True, "same"),
        ("model4-event_round4", True, "same"),
        ("model4-eventprimes_round1", True, "20/20 cells, kind=primes throughout, no short cells"),
        ("model4-eventprimes_round2", True, "same"),
        ("model4-eventprimes_round3", True, "same"),
        ("model4-eventprimes_round4", True, "same"),
        # "model4-event" (bare, no round suffix) is a 1-cell debug leftover,
        # not a real round -- deliberately not included.
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
