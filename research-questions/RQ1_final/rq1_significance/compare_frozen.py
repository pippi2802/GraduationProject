#!/usr/bin/env python3
"""Compare tests.csv with the settings that have an effect in the frozen results (results_final/table_*.csv).

The frozen outputs carry no explicit "effect" label. Operational rule used here: a setting has an effect at a placement when its tail spread is at
least twice that of full isolation (relative_spread >= 2) in at least one measured cell. The frozen values fall into two clearly separated groups
(>= 9.4 or <= 1.62), so the rule does not depend on the exact threshold between 1.7 and 9.
"""
import pathlib
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE.parent / "os-experiments" / "results_final"
THRESH = 2.0

tests = pd.read_csv(HERE / "tests.csv")
rows = []
for placement in ["single-core", "multi-core"]:
    t = pd.read_csv(FROZEN / f"table_{placement}.csv")
    t = t[t.configuration != "full isolation"].dropna(subset=["jobs"])
    for config, g in t.groupby("configuration"):
        sub = tests[(tests.placement == placement) & (tests.configuration == config)].set_index("metric")
        frozen_effect = bool(g.relative_spread.max() >= THRESH)
        test_sig = bool(sub.significant.any())
        rows.append(dict(placement=placement, configuration=config, frozen_max_relative_spread=g.relative_spread.max(), frozen_max_miss_rate_pct=g.miss_rate_pct.max(),
                         frozen_effect=frozen_effect, p_holm_S=sub.loc["S", "p_holm"], p_holm_M=sub.loc["M", "p_holm"], test_significant=test_sig,
                         agree=frozen_effect == test_sig))
out = pd.DataFrame(rows)
out.to_csv(HERE / "comparison_frozen.csv", index=False, float_format="%.6g")
print(out.round(4).to_string())
print("\ndisagreements:\n", out[~out.agree][["placement", "configuration", "frozen_effect", "test_significant"]].to_string())
