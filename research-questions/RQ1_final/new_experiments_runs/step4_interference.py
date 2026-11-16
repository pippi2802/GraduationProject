#!/usr/bin/env python3
"""STEP 4 - interference table. Per run, then median over the 4 rounds (and min-max), per configuration x cell.
Q = U * P. Execution time of a job = finish_us - start_us.
  dispatch_p99_ratio     p99 of dispatch_latency_us (jobs with C > Q excluded) / the same for full isolation (same placement, P, U, round)
  interrupts_per_s       jobs with mid_job_preempt_us > 10 us (jobs with C > Q excluded) / sum of execution time of the jobs kept [s]
  nonvol_ctxt_per_s      sum of nonvol_ctxt (all jobs) / sum of execution time of all jobs [s]
  median_C_ratio         median C / median C of full isolation (same placement, P, U, round)
  cv_C                   std(C) / mean(C) (sample std) over all jobs
  share_miss_C_gt_Q      jobs with deadline_miss = 1 and C > Q / jobs with deadline_miss = 1 (undefined without a miss; the median is over the rounds with a miss)
Writes output/step4_runs.csv, output/step4_interference.csv, output/step4_interference_<placement>.tex (one table per metric).
"""
import numpy as np
import pandas as pd

import common as cm

METRICS = [("dispatch_p99_ratio", "Dispatch latency p99 / full isolation", 2),
           ("interrupts_per_s", "Interruptions per second of execution", 2),
           ("nonvol_ctxt_per_s", "Involuntary context switches per second of execution", 2),
           ("median_C_ratio", "Median $C$ / full isolation", 3),
           ("cv_C", "CV of $C$", 4),
           ("share_miss_C_gt_Q", "Share of misses with $C > Q$", 2)]


def per_run():
    runs, _ = cm.get_runs()
    rows = []
    for (pl, c, s, u, r), a in runs.items():
        P = cm.PERIOD[s]
        Q = u * P
        C = a["C_cputime_us"]
        ex = a["finish_us"] - a["start_us"]
        keep = C <= Q
        ex_keep = ex[keep].sum() / 1e6
        miss = a["deadline_miss"] == 1
        rows.append(dict(placement=pl, configuration=c, scale=s, U=u, round=r,
                         dispatch_p99_us=float(np.percentile(a["dispatch_latency_us"][keep], 99)) if keep.any() else np.nan,
                         interrupts_per_s=float((a["mid_job_preempt_us"][keep] > cm.INTERRUPT_US).sum() / ex_keep) if ex_keep > 0 else np.nan,
                         nonvol_ctxt_per_s=float(a["nonvol_ctxt"].sum() / (ex.sum() / 1e6)),
                         median_C_us=float(np.median(C)), cv_C=float(np.std(C, ddof=1) / np.mean(C)),
                         n_miss=int(miss.sum()), n_miss_C_gt_Q=int((miss & (C > Q)).sum()), n_C_gt_Q=int((~keep).sum()),
                         share_miss_C_gt_Q=float((miss & (C > Q)).sum() / miss.sum()) if miss.any() else np.nan))
    t = pd.DataFrame(rows)
    fi = t[t.configuration == cm.FULL].set_index(["placement", "scale", "U", "round"])
    k = list(zip(t.placement, t.scale, t.U, t["round"]))
    t["dispatch_p99_ratio"] = t.dispatch_p99_us.to_numpy() / fi.dispatch_p99_us.reindex(k).to_numpy()
    t["median_C_ratio"] = t.median_C_us.to_numpy() / fi.median_C_us.reindex(k).to_numpy()
    return t


def main():
    t = per_run()
    t.to_csv(cm.OUT / "step4_runs.csv", index=False)
    agg = []
    for (pl, c, s, u), g in t.groupby(["placement", "configuration", "scale", "U"], sort=False):
        row = dict(placement=pl, configuration=c, scale=s, U=u, n_rounds=len(g))
        for m, _, _ in METRICS:
            v = g[m].dropna()
            row[f"{m}_median"] = float(v.median()) if len(v) else np.nan
            row[f"{m}_min"] = float(v.min()) if len(v) else np.nan
            row[f"{m}_max"] = float(v.max()) if len(v) else np.nan
            row[f"{m}_n"] = len(v)
        agg.append(row)
    a = pd.DataFrame(agg)
    a.to_csv(cm.OUT / "step4_interference.csv", index=False)

    for pl, slug, title, *_ in cm.PLACEMENTS:
        sub = a[a.placement == pl].set_index(["configuration", "scale", "U"])
        tabs = []
        for m, name, nd in METRICS:
            def get(c, s, u, m=m, nd=nd):
                if not cm.planned(c, u):
                    return "n/r"
                r = sub.loc[(c, s, u)]
                if np.isnan(r[f"{m}_median"]):
                    return "--"
                return f"{r[f'{m}_median']:.{nd}f} [{r[f'{m}_min']:.{nd}f}--{r[f'{m}_max']:.{nd}f}]"
            cap = (f"{name}, {pl}: median over the four rounds [minimum--maximum]. "
                   + ("Dispatch latency and interruptions exclude jobs with $C > Q$ ($Q = UP$); an interruption is a job with mid-job preemption above $10\\,\\mu$s. " if m in ("dispatch_p99_ratio", "interrupts_per_s") else "")
                   + ("Median over the rounds that have a miss. " if m == "share_miss_C_gt_Q" else "") + "n/r: not run; --: undefined.")
            tabs.append(cm.grid_tex(cm.CONFIGS, get, cap, f"tab:rq1-rerun-interference-{m}-{pl}", small=True))
        (cm.OUT / f"step4_interference_{pl}.tex").write_text("\n".join(tabs))
    print(f"step 4: {len(t)} runs, {len(a)} cells")
    return 0


if __name__ == "__main__":
    main()
