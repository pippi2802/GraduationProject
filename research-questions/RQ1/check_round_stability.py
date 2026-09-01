#!/usr/bin/env python3
"""check_round_stability.py <round1> <round2> ... -- eyeball miss_rate/R_p50
side by side across rounds, per scale/U, BEFORE pooling. A round whose
numbers don't match its siblings at the same U is a candidate for the kind
of contamination found in model3-w2_sib_res_round3 (wrong arm silently
mixed in) -- check its placement.json/log before trusting it."""
import sys, pandas as pd
from pathlib import Path

rounds = sys.argv[1:]
if not rounds:
    sys.exit("usage: check_round_stability.py <round1> <round2> ...")

dfs = []
for r in rounds:
    f = Path("analysis") / r / "summary.csv"
    if not f.exists():
        print(f"[skip] {f} missing -- run `python result.py {r}` first")
        continue
    d = pd.read_csv(f)[["scale", "U", "n", "miss_rate", "R_p50"]]
    d["round"] = r
    dfs.append(d)

df = pd.concat(dfs, ignore_index=True)
for metric in ["n", "miss_rate", "R_p50"]:
    print(f"\n=== {metric} ===")
    piv = df.pivot_table(index=["scale", "U"], columns="round", values=metric)
    print(piv.to_string())
