"""Checks on the data themselves: DataSummary, PFloor (stalls no budget removes) and PlatformEvents (coincident extremes across instances)."""
import numpy as np
import pandas as pd

from config import ROLES
from report import check


class DataSummary:
    """Per run and instance: jobs, skipped, late (response > T), and the median / p99 / max of C. Shows the data are complete."""

    def run(self, scenarios):
        rows = []
        for s in scenarios:
            for run_id, (run, _) in s.runs.items():
                for inst in s.instances:
                    df, x = run.frames[inst], run.C(inst)
                    late = int(((df.skipped == 0) & (df.response_ns > s.period_ms * 1e6)).sum())
                    rows.append(dict(scenario=s.name, run=run_id, instance=inst, T_ms=s.period_ms, jobs=len(x), skipped=int((df.skipped == 1).sum()), late=late,
                                     C_median=np.median(x), C_p99=np.quantile(x, .99), C_max=x.max()))
        t = pd.DataFrame(rows).set_index(["scenario", "run", "instance"])
        small = t[t.jobs < 20000]
        return t, [check("every run has enough jobs for p = 1e-3 (>= 20000)", small.empty,
                         "all runs ok" if small.empty else f"{len(small)} run(s) have fewer than 20000 jobs")]


class PFloor:
    """p_floor: the stalls and late jobs that remain with a generous budget (VM stalls, late starts). A job is bad when it was skipped
    or late; an event is a run of consecutive bad jobs (one stall that skips 56 jobs counts once), merged across the instances of a run.
    Tolerances below the bad-job rate are not meaningful."""

    def __init__(self, cfg, bound):
        self.cfg, self.bound = cfg, bound

    def run(self, scenarios):
        rows = []
        for s in scenarios:
            groups = {"profiling runs": s.ids("baseline", "stress"), "extra baselines": s.ids("extra_baseline")}
            groups["all runs"] = groups["profiling runs"] + groups["extra baselines"]
            for label, run_ids in groups.items():
                if not run_ids:
                    continue
                jobs = bad_jobs = events = longest = 0
                for run_id in run_ids:
                    run, bads = s.run(run_id), []
                    for inst in s.instances:
                        df = run.frames[inst][run.frames[inst].warmup == 0]
                        bad = (df.skipped == 1).to_numpy() | ((df.skipped == 0) & (df.response_ns > s.period_ms * 1e6)).to_numpy()
                        bads.append(bad)
                        jobs += len(df)
                        bad_jobs += int(bad.sum())
                    u = np.logical_or.reduce(bads)                                      # an event hits all the instances of a run together
                    first = u & ~np.concatenate(([False], u[:-1]))
                    events += int(first.sum())
                    if u.any():
                        longest = max(longest, int(np.bincount(np.cumsum(first)[u]).max()))
                rows.append({"scenario": s.name, "runs": label, "jobs": jobs, "events": events, "event rate": events / jobs,
                             "95% upper": self.bound.cp_upper(events, jobs), "bad-job rate": bad_jobs / jobs, "longest event (jobs)": longest})
        t = pd.DataFrame(rows).set_index(["scenario", "runs"])
        worst = t["bad-job rate"].max()
        return t, [check("p_floor below the smallest tolerance", worst < min(self.cfg.tolerances),
                         f"worst bad-job rate {worst:.1e} against p = {min(self.cfg.tolerances):g}")]


class PlatformEvents:
    """Multi-instance scenarios run the same content in step, so a job that is slow on all instances at the same time points to the
    platform, not to the task. A job whose residual (C minus the median C of its frame) is above thr_ms is a candidate; candidates that
    overlap in time across the first two instances are coincident events. Compared: the GEV shape xi with and without them."""

    def __init__(self, cfg, tail):
        self.cfg, self.tail = cfg, tail
        self.rng = np.random.default_rng(1)

    @staticmethod
    def overlap_mask(sa, ea, sb, eb):
        """for each interval [sa, ea]: does any interval [sb, eb] overlap it?"""
        out = np.zeros(len(sa), dtype=bool)
        if len(sa) == 0 or len(sb) == 0:
            return out
        o = np.argsort(sb)
        sb, eb = sb[o], eb[o]
        pm = np.maximum.accumulate(eb)
        hi = np.searchsorted(sb, ea, side="right")
        ok = hi > 0
        out[ok] = pm[hi[ok] - 1] >= sa[ok]
        return out

    def run(self, scenario):
        if len(scenario.instances) < 2:
            return None, []
        base = scenario.run("baseline1").executed(scenario.instances[0])
        if not {"frame_idx", "start_ns", "end_ns"} <= set(base.columns) or base.groupby("frame_idx").size().min() < 2:
            return None, [check(f"platform events ({scenario.name})", None, "not applicable: needs start_ns, end_ns and frames that repeat during the run")]
        ia, ib = scenario.instances[:2]
        rows = []
        for role in ROLES:
            d = {}
            for inst in (ia, ib):
                df = scenario.run(role).executed(inst).reset_index(drop=True)
                df["C"] = df.cpu_ns / 1e6
                df["resid"] = df.C - df.groupby("frame_idx").C.transform("median")
                df["event"] = False
                d[inst] = df
            a, b = d[ia][d[ia].resid > self.cfg.thr_ms], d[ib][d[ib].resid > self.cfg.thr_ms]
            sa, ea, sb, eb = a.start_ns.to_numpy(), a.end_ns.to_numpy(), b.start_ns.to_numpy(), b.end_ns.to_numpy()
            ma, mb = self.overlap_mask(sa, ea, sb, eb), self.overlap_mask(sb, eb, sa, ea)
            d[ia].loc[a.index[ma], "event"] = True
            d[ib].loc[b.index[mb], "event"] = True
            t0 = min(d[ia].start_ns.min(), d[ib].start_ns.min())
            span = max(d[ia].end_ns.max(), d[ib].end_ns.max()) - t0
            null = np.array([self.overlap_mask(sa, ea, (sb - t0 + o) % span + t0, (sb - t0 + o) % span + t0 + (eb - sb)).sum()
                             for o in self.rng.integers(0, span, self.cfg.n_shift)])
            pval = (1 + np.sum(null >= ma.sum())) / (1 + self.cfg.n_shift)
            for inst in (ia, ib):
                x_all, x_clean = d[inst].C.to_numpy(), d[inst].C[~d[inst].event].to_numpy()
                fa, fc = self.tail.fit(self.tail.block_maxima(x_all)), self.tail.fit(self.tail.block_maxima(x_clean))
                rows.append(dict(scenario=scenario.name, run=role, instance=inst, candidates=int((d[inst].resid > self.cfg.thr_ms).sum()),
                                 coincident=int(d[inst].event.sum()), chance=null.mean(), p_value=pval, xi_with=fa["xi"], xi_without=fc["xi"]))
        t = pd.DataFrame(rows).set_index(["scenario", "run", "instance"])
        real = int((t.groupby("run").p_value.first() < 0.05).sum())
        return t, [check(f"platform events ({scenario.name})", None, f"coincident extremes are not chance in {real} of {len(ROLES)} runs (p < 0.05)")]


class NoiseFloorCheck:
    """P3: the cost of the runtime itself at the chosen period (empty job), against the task: the overhead as a share of the median C,
    the dispatch latency as a share of the period. Reported, it does not change the budgets."""

    def run(self, scenarios, noise):
        if noise is None:
            return None, [check("noise floor", None, "not measured (optional): step 1, --noise-period-ms")]
        n = noise.iloc[0]
        rows, checks = [], []
        for s in scenarios:
            c_med = float(np.median(np.concatenate([s.series("baseline1", i) for i in s.instances])))
            ov, dl = n.overhead_us_median / 1e3 / c_med * 100, n.dispatch_us_p99 / 1e3 / s.period_ms * 100
            rows.append(dict(scenario=s.name, task_period_ms=s.period_ms, noise_period_ms=n.period_ms, overhead_us_median=n.overhead_us_median,
                             overhead_pct_of_C=ov, dispatch_us_p99=n.dispatch_us_p99, dispatch_pct_of_T=dl, dispatch_us_max=n.dispatch_us_max))
            same = abs(n.period_ms - s.period_ms) <= 0.01 * s.period_ms
            checks.append(check(f"noise floor ({s.name})", None, f"empty-job overhead {n.overhead_us_median:.1f} us = {ov:.3f}% of the median C; dispatch latency "
                                f"p99 {n.dispatch_us_p99:.0f} us = {dl:.2f}% of T" + ("" if same else f"; measured at T = {n.period_ms} ms, not {s.period_ms:.3f} ms")))
        return pd.DataFrame(rows).set_index("scenario"), checks
