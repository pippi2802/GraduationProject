"""The data: Run (one run of a scenario) and Scenario (all the runs of one scenario)."""
import numpy as np
import pandas as pd

from config import ROLES, BASELINES, STRESS

REQUIRED = ["job_id", "skipped", "warmup", "cpu_ns", "release_ns", "response_ns"]      # columns every CSV must have
OPTIONAL = ["start_ns", "end_ns", "frame_idx"]                                          # only the platform-event check needs these


class Run:
    """One run of one scenario: one table per instance. C = CPU time of the executed, non-warm-up jobs, in ms, in job order."""

    def __init__(self, label, sources):
        self.label = label
        self.frames = {}
        for i, src in enumerate(sources):
            df = src.copy() if isinstance(src, pd.DataFrame) else pd.read_csv(src)
            missing = [c for c in REQUIRED if c not in df.columns]
            if missing:
                raise ValueError(f"{label}, instance{i}: missing columns {missing} (needed: {REQUIRED})")
            self.frames[f"instance{i}"] = df.sort_values("job_id").reset_index(drop=True)

    @property
    def instances(self):
        return list(self.frames)

    def executed(self, inst):
        df = self.frames[inst]
        return df[(df.skipped == 0) & (df.warmup == 0) & df.cpu_ns.notna()]

    def C(self, inst):
        return self.executed(inst).cpu_ns.to_numpy() / 1e6

    def infer_period_ms(self):
        d = np.diff(self.frames[self.instances[0]].release_ns.to_numpy())
        if len(d) < 2 or np.median(d) <= 0 or d.std() > 0.01 * np.median(d):
            raise ValueError(f"{self.label}: release_ns is not periodic, so the period cannot be inferred: state period_ms")
        return float(np.median(d)) / 1e6


class Scenario:
    """All the runs of one scenario. run ids: the four roles, "extra:<label>" and "stress_run"; kinds: baseline, stress,
    extra_baseline, stress_run."""

    def __init__(self, spec, period_ms=None):
        self.name = spec.name
        self.runs = {role: (Run(f"{spec.name}/{role}", spec.runs[role]), "baseline" if role in BASELINES else "stress") for role in ROLES}
        for label, src in spec.extra_baselines.items():
            self.runs[f"extra:{label}"] = (Run(f"{spec.name}/extra:{label}", src), "extra_baseline")
        if spec.stress_run:
            self.runs["stress_run"] = (Run(f"{spec.name}/stress_run", spec.stress_run), "stress_run")
        self.instances = self.runs["baseline1"][0].instances
        for run_id, (run, _) in self.runs.items():
            if run.instances != self.instances:
                raise ValueError(f"{spec.name}/{run_id}: {len(run.instances)} instances, baseline1 has {len(self.instances)}")
        self.m = spec.m or (3 if len(self.instances) == 1 else 2)
        self.stress_baseline = f"extra:{spec.stress_baseline}" if spec.stress_baseline else None
        if self.stress_baseline and self.stress_baseline not in self.runs:
            raise ValueError(f"{spec.name}: stress_baseline '{spec.stress_baseline}' is not one of the extra baselines {list(spec.extra_baselines)}")
        self.period_ms = period_ms or self.runs["baseline1"][0].infer_period_ms()

    def run(self, run_id):
        return self.runs[run_id][0]

    def ids(self, *kinds):
        return [r for r, (_, k) in self.runs.items() if k in kinds]

    def series(self, run_id, inst):
        return self.run(run_id).C(inst)
