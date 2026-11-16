#!/usr/bin/env python3
"""STEP 5 - throttle test. For missed jobs (deadline_miss = 1) with C <= Q (Q = U * P): the share whose mid_job_preempt_us lies within 10% of (P - Q),
i.e. |mid_job_preempt_us - (P - Q)| <= 0.1 * (P - Q). Per configuration x cell, the four rounds pooled.
Writes output/step5_throttle.csv and output/step5_throttle_<placement>.tex.
"""
import numpy as np
import pandas as pd

import common as cm


def main():
    runs, _ = cm.get_runs()
    acc = {}
    for (pl, c, s, u, r), a in runs.items():
        P = cm.PERIOD[s]
        Q = u * P
        sel = (a["deadline_miss"] == 1) & (a["C_cputime_us"] <= Q)
        mid = a["mid_job_preempt_us"][sel]
        near = np.abs(mid - (P - Q)) <= cm.THROTTLE_TOL * (P - Q)
        n0, n1 = acc.get((pl, c, s, u), (0, 0))
        acc[(pl, c, s, u)] = (n0 + int(sel.sum()), n1 + int(near.sum()))
    rows = []
    for (pl, c, s, u), (n, k) in acc.items():
        rows.append(dict(placement=pl, configuration=c, scale=s, U=u, P_minus_Q_us=cm.PERIOD[s] * (1 - u), missed_C_le_Q=n, near_P_minus_Q=k,
                         share=(k / n) if n else np.nan))
    t = pd.DataFrame(rows)
    t.to_csv(cm.OUT / "step5_throttle.csv", index=False)
    for pl, slug, title, *_ in cm.PLACEMENTS:
        sub = t[t.placement == pl].set_index(["configuration", "scale", "U"])

        def get(c, s, u):
            if not cm.planned(c, u):
                return "n/r"
            r = sub.loc[(c, s, u)]
            return "--" if r.missed_C_le_Q == 0 else f"{100 * r.share:.0f}\\% ({int(r.near_P_minus_Q)}/{int(r.missed_C_le_Q)})"
        cap = (f"Throttle test, {pl}: among the missed jobs with $C \\le Q$, the share whose mid-job preemption lies within 10\\% of $P-Q$ "
               f"(number of such jobs in brackets, the four rounds pooled). --: no missed job with $C \\le Q$. n/r: not run.")
        (cm.OUT / f"step5_throttle_{pl}.tex").write_text(cm.grid_tex(cm.CONFIGS, get, cap, f"tab:rq1-rerun-throttle-{pl}", small=True))
    print(f"step 5: {len(t)} cells; cells with at least one missed job with C <= Q: {int((t.missed_C_le_Q > 0).sum())}")
    return 0


if __name__ == "__main__":
    main()
