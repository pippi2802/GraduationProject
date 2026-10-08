"""Parameters of the procedure and the description of the data a practitioner provides."""
import json
from dataclasses import dataclass, field
from pathlib import Path

ROLES = ("baseline1", "cache", "memory", "baseline2")          # the four profiling runs of a scenario
BASELINES, STRESS = ("baseline1", "baseline2"), ("cache", "memory")


@dataclass
class ScenarioInput:
    """The data of one scenario (single-core, multi-core, ...).

    Every run is a list with one entry per instance, and every entry is a CSV path or a DataFrame, in the same instance order
    in all runs. `runs` has the four profiling runs (baseline1, cache, memory, baseline2). `extra_baselines` are further
    baseline runs under any label of your choice (other times, other machines: the procedure does not need to know which).
    `stress_run` is one more stressed run; `stress_baseline` is the label of the extra baseline measured next to it.
    `m` is the number of enemy cores of the profiling; step 2 records it, otherwise 3 for one instance and 2 for several.
    """
    name: str
    runs: dict
    extra_baselines: dict = field(default_factory=dict)
    stress_run: list = None
    stress_baseline: str = None
    m: int = None

    @classmethod
    def from_steps(cls, name, profiling_dir, extra_dir=None, m=None, stress_baseline=None):
        """Step 2 results: <profiling_dir>/{baseline1,cache,memory,baseline2}/instance*.csv and profiling.json (the enemy cores m).
        Step 3 results: <extra_dir>/extra_baselines/<label>/ and <extra_dir>/stress_run/ (with paired_with.txt). Arguments override the files."""
        p = Path(profiling_dir)
        files = lambda d: sorted(Path(d).glob("instance*.csv"))
        runs = {role: files(p / role) for role in ROLES}
        missing = [str(p / r) for r, f in runs.items() if not f]
        if missing:
            raise FileNotFoundError(f"{name}: no instance*.csv in {missing}: run step 2 first")
        extras, stress, paired = {}, None, None
        if extra_dir and Path(extra_dir).is_dir():
            e = Path(extra_dir)
            extras = {d.name: files(d) for d in sorted((e / "extra_baselines").glob("*")) if d.is_dir() and files(d)}
            stress = files(e / "stress_run") or None
            if (e / "stress_run" / "paired_with.txt").exists():
                paired = (e / "stress_run" / "paired_with.txt").read_text().strip()
        if m is None and (p / "profiling.json").exists():
            m = json.loads((p / "profiling.json").read_text())["m"]
        return cls(name, runs, extras, stress, stress_baseline or paired, m)


@dataclass
class Config:
    scenarios: list                         # ScenarioInput, one per scenario to analyse
    platform_table: object = None           # step 1's platform_factor.csv (path or DataFrame): alpha_platform(m)
    platform_factors: dict = None           # optional explicit {m: factor}, takes precedence over the table
    noise_floor: object = None              # step 1's noise_floor_summary.csv (path or DataFrame), optional
    period_ms: float = None                 # task period T; inferred from release_ns when None
    out_dir: str = "results"
    show_figures: bool = False
    tolerances: tuple = (1e-1, 1e-2, 1e-3)  # tolerances p: a budget Q is valid when P(C > Q) <= p (not a deadline-miss rate)
    test_tolerances: tuple = (1e-2, 1e-3)   # the p used in the pass tests and the replays
    block: int = 600                        # block maxima size (jobs)
    p_gev: float = 1e-3                     # the GEV bound is computed at this p only
    runs_r: int = 50                        # runs-method gap (jobs) between clusters of exceedances
    l_boot: int = 600                       # moving-block bootstrap block length (jobs)
    n_boot: int = 300
    alpha: float = 0.05                     # one-sided 95% upper confidence bound
    hwm_p: float = 1e-3                     # p of the alpha_drift used by the high-water mark route
    admission_max: float = 0.95             # Q / T must not exceed this
    k_list: tuple = (10, 100)               # window lengths of the worst-case (m, k)
    thr_ms: float = 1.0                     # residual above this (ms) = candidate platform event
    n_shift: int = 200                      # shifted replicates of the platform-event null
