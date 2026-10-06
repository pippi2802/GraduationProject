"""Step 4: from the data of steps 1, 2 and 3 to the budgets of the three routes, with their validation on the data.

    python main.py                       every scenario found in step 2's results
    python main.py --scenarios single_core --m single_core=3 --out results

It reads, without being told any path:
    ../step1_platform/results/platform_factor.csv       alpha_platform(m)                (and noise_floor_summary.csv, optional)
    ../step2_profiling/results/<scenario>/               baseline1, cache, memory, baseline2, profiling.json (the enemy cores m)
    ../step3_drift_runs/results/<scenario>/              extra_baselines/<label>/, stress_run/ (+ paired_with.txt), optional
It prints the tables, saves each as CSV and each figure as PNG in results/, and ends with a validity summary.
results/budgets.csv (scenario, route, p, Q_ms, runtime_us, period_us ...) is what step 5 validates online.

To change a default permanently, edit DEFAULTS below. The period T is inferred from release_ns; the tolerances are in config.py."""
import argparse
from pathlib import Path

from config import Config, ScenarioInput
from procedure import Procedure

HERE = Path(__file__).resolve().parent
DEFAULTS = dict(
    steps_dir=HERE.parent,        # the folder with step1_platform ... step3_drift_runs
    scenarios=None,               # None = every folder of step2_profiling/results
    m={},                         # {"single_core": 3}: enemy cores, only to override what step 2 recorded
    stress_baseline={},           # {"single_core": "vm2"}: only to override step3's paired_with.txt
    platform_factors={},          # {1: 1.03, 2: 1.06, 3: 1.11}: explicit factors, take precedence over step 1's table
    period_ms=None,
)


def pairs(items, cast=str):
    return {k: cast(v) for k, v in (i.split("=", 1) for i in items or [])}


def parse():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps-dir", default=str(DEFAULTS["steps_dir"]))
    ap.add_argument("--scenarios", nargs="+", default=DEFAULTS["scenarios"], help="names used in step 2 (default: all found)")
    ap.add_argument("--m", nargs="+", metavar="SCENARIO=M", help="enemy cores per scenario, overrides step 2's profiling.json")
    ap.add_argument("--stress-baseline", nargs="+", metavar="SCENARIO=LABEL", help="overrides step 3's paired_with.txt")
    ap.add_argument("--platform-factors", nargs="+", metavar="M=FACTOR", help="explicit alpha_platform(m), overrides step 1's table")
    ap.add_argument("--period-ms", type=float, default=DEFAULTS["period_ms"], help="task period; inferred from release_ns by default")
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--show", action="store_true", help="show the figures as well as saving them")
    return ap.parse_args()


def main():
    a = parse()
    steps = Path(a.steps_dir)
    step2, step3, step1 = steps / "step2_profiling" / "results", steps / "step3_drift_runs" / "results", steps / "step1_platform" / "results"
    names = a.scenarios or (sorted(d.name for d in step2.iterdir() if d.is_dir()) if step2.is_dir() else [])
    if not names:
        raise SystemExit(f"no scenario found in {step2}: run step 2 first (or name the scenarios with --scenarios)")
    m, paired = {**DEFAULTS["m"], **pairs(a.m, int)}, {**DEFAULTS["stress_baseline"], **pairs(a.stress_baseline)}
    scenarios = [ScenarioInput.from_steps(n, step2 / n, step3 / n, m=m.get(n), stress_baseline=paired.get(n)) for n in names]
    table, noise = step1 / "platform_factor.csv", step1 / "noise_floor_summary.csv"
    factors = {**DEFAULTS["platform_factors"], **pairs(a.platform_factors, float)}
    cfg = Config(scenarios=scenarios, platform_table=table if table.exists() else None, noise_floor=noise if noise.exists() else None,
                 platform_factors={int(k): v for k, v in factors.items()} or None, period_ms=a.period_ms, out_dir=a.out, show_figures=a.show)
    if cfg.platform_table is None and cfg.platform_factors is None:
        print(f"note: no {table} (step 1) and no --platform-factors: Route 2b will be skipped")
    Procedure(cfg).run()


if __name__ == "__main__":
    main()
