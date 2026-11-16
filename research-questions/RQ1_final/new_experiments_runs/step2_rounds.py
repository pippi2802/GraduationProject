#!/usr/bin/env python3
"""STEP 2 - rounds. Needs output/step1_runs.csv.
Per cell (placement, configuration, scale, U): number of rounds whose miss+skip rate EXCEEDS (strictly) the maximum of the four
full-isolation rounds of the same placement, scale and U (x/4). Per cell: min-max of full isolation over the rounds.
Writes output/step2_rounds.csv (configurations), output/step2_fi_range.csv (full isolation), output/step2_rounds_<placement>.tex.
"""
import numpy as np
import pandas as pd

import common as cm


def main():
    t = pd.read_csv(cm.OUT / "step1_runs.csv")
    fi = t[t.configuration == cm.FULL].groupby(["placement", "scale", "U"]).miss_skip_pct.agg(fi_min="min", fi_max="max").reset_index()
    fi.to_csv(cm.OUT / "step2_fi_range.csv", index=False)
    mx = fi.set_index(["placement", "scale", "U"]).fi_max
    rows = []
    for (pl, c, s, u) in cm.cells():
        if c == cm.FULL:
            continue
        g = t[(t.placement == pl) & (t.configuration == c) & (t.scale == s) & (t.U == u)].sort_values("round")
        ref = mx[(pl, s, u)]
        rows.append(dict(placement=pl, configuration=c, scale=s, U=u, n_rounds=len(g), x_exceed=int((g.miss_skip_pct > ref).sum()),
                         fi_max_pct=ref, **{f"round{int(r)}_pct": v for r, v in zip(g["round"], g.miss_skip_pct)}))
    x = pd.DataFrame(rows)
    x.to_csv(cm.OUT / "step2_rounds.csv", index=False)

    for pl, slug, title, *_ in cm.PLACEMENTS:
        xs = x[x.placement == pl].set_index(["configuration", "scale", "U"])
        fs = fi[fi.placement == pl].set_index(["scale", "U"])

        def get(c, s, u):
            if not cm.planned(c, u):
                return "n/r"
            if c == cm.FULL:
                r = fs.loc[(s, u)]
                return f"{r.fi_min:.3f}--{r.fi_max:.3f}"
            return f"{int(xs.loc[(c, s, u)].x_exceed)}/{int(xs.loc[(c, s, u)].n_rounds)}"
        cap = (f"Rounds above full isolation, {pl}. For every configuration and cell, the number of the four rounds whose miss+skip rate "
               f"(lost releases over all releases of the run, in percent) is strictly larger than the maximum over the four full-isolation rounds of the same cell. "
               f"The full-isolation row gives the minimum--maximum of its four rounds in percent. n/r: not run.")
        (cm.OUT / f"step2_rounds_{pl}.tex").write_text(cm.grid_tex(cm.CONFIGS, get, cap, f"tab:rq1-rerun-rounds-{pl}"))
    print(f"step 2: {len(x)} configuration cells; cells with x = n_rounds: {int((x.x_exceed == x.n_rounds).sum())}, with x = 0: {int((x.x_exceed == 0).sum())}")
    return 0


if __name__ == "__main__":
    main()
