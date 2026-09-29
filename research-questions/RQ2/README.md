# RQ2: deriving KubeDeadline reservation parameters from measurement

A measurement-based procedure to derive CBS reservation parameters
(budget Q, period T, deadline D = T, core count m) for a periodic
real-time video-frame task running under KubeDeadline on Azure, and to
validate them. See `docs/procedure.md` for the full procedure (Steps 1-5)
and `docs/data_layout.md` for the results file layout and JSON schemas.

Status: Batch 1 (repo structure + experiment infrastructure) is in place.
Batches 2 (procedure/analysis) and 3 (validation/reporting) land next; see
`rq2/procedure`, `rq2/validation`, `rq2/reporting` for their current (empty
package) state.

## Layout

```
configs/        platform.yaml, requirements.yaml, campaign_*.yaml, session_profiling.yaml
templates/      pod_template.yaml (grounded in the real KubeDeadline CRD pattern - see below)
rq2/            importable Python package
  common/       io.py, metrics.py, paths.py, manifest.py - shared by every stage
  workload/     rt_video.py, launch.py, analyze.py, replay.py (the measured task)
  orchestration/ node_exec.py, pod_gen.py, campaign.py, checks.py, session.py
  procedure/    tail_estimation.py, inflation.py, cbs_model.py, budget.py, ... (Batch 2)
  validation/   validate.py (Batch 3)
  reporting/    figures.py, tables.py (Batch 3)
stress/         enemy.c, victim.c, Makefile, hk_load.sh, enemy_effectiveness.sh
tools/          platform_info.sh, osnoise_capture.sh, run_tests.sh
tests/          pytest, one file per module, synthetic data only
docs/           procedure.md, data_layout.md
results/        raw/, derived/, figures/, tables/ (git-ignored, kept via .gitkeep)
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
make build   # compiles stress/enemy.c and pip installs requirements.txt
```

## Record the platform

```bash
tools/platform_info.sh
```

Writes `results/derived/platform/platform_info.json` and fills in
`configs/platform.yaml`'s `llc_size_kb`.

## Running a stage

```bash
make test               # builds stress/{enemy,victim} then runs pytest (tools/run_tests.sh)
make session             # unattended profiling session, --dry-run by default
make session DRY_RUN=    # the real thing - review the dry-run plan first
make profile             # the older dial-level profiling campaign, --dry-run by default
make profile DRY_RUN=    # the real thing - review the dry-run plan first
make analyze              # Step 2/3: tail estimation + inflation (Batch 2)
make budget                # Step 4: derive results/derived/budget/budgets.json (Batch 2)
make validate                # validation campaign + Step 5 checks (Batch 2/3)
make report                    # figures + LaTeX tables (Batch 3)
```

Every orchestration script accepts `--dry-run`, which only prints the
commands it would run (kubectl, ssh, enemy/hk_load start-stop) - nothing
touches a live cluster unless you drop that flag deliberately. Note:
`manifest.json` writes are NOT gated by `--dry-run` (that's how resumability
demos work in tests) - a dry-run of `session.py`/`campaign.py` does leave
manifest stubs under `results/raw/<session>/`, delete that session directory
before a real run if you don't want it treating those runs as already done.

## Running a profiling session

`rq2/orchestration/session.py` runs a whole profiling session unattended,
on the same VM it profiles: preflight checks -> platform info -> a one-time
enemy-effectiveness test (proves the enemies actually interfere,
independent of the workload) -> the ordered runs from
`configs/session_profiling.yaml` (`baseline -> cache -> memory ->
baseline_end`, per deployment) -> per-run data-quality checks -> a session
report.

```bash
make session                          # --dry-run: prints the full planned action sequence
make session DRY_RUN=                 # runs for real, on this machine
make session CONFIG=configs/my.yaml DRY_RUN=
```

A run that fails its post-run checks is retried once; if it fails again
it's marked `invalid` in its manifest and the session continues. Re-running
`session.py` on the same session name skips any run whose manifest already
says `complete` (resumable after a crash or a manual stop).

### Reading `results/raw/<session>/session_report.md`

Three PASS/WARN/FAIL sections: **Preflight** (abort conditions - if this
session ran at all, preflight passed), **Enemy effectiveness** (did the
enemies actually slow the matching victim down), and one block **per run**
with its post-run checks. `session_report.json` has the same data plus the
raw per-sample monitoring log, for scripting.

| Check | On FAIL / WARN, try |
| --- | --- |
| `cpu_count` / `threads_per_core` | Wrong VM size, or SMT got re-enabled - check the Azure VM spec |
| `isolation_cmdline` (WARN) | Add `isolcpus`/`nohz_full`/`rcu_nocbs` for the RT cores to the kernel cmdline and reboot |
| `stray_threads_on_rt_cores` | Something else is scheduled on an isolated core - find and pin/move it before profiling |
| `no_skipped_jobs` | Budget factor too tight or frame too heavy for the period - raise `profiling_budget_factor` or lower `--work`/frame size |
| `release_spacing` | Clock/scheduling issue on the node - check `steal_time`, host load |
| `realtime_setup_flags` | mlockall/SCHED_FIFO/affinity failed in the pod - check `SYS_NICE`/`IPC_LOCK` capabilities and privileges |
| `vm_stalls` (WARN) | Some jobs stalled hard (cloud noisy-neighbour) - inspect those jobs, consider re-running that condition |
| `stationarity` (WARN) | The task's timing drifted mid-run - longer runs may need periodic re-baselining |
| `interference_effect` (WARN, "no measurable interference effect") | Not necessarily a problem - the workload may genuinely be insensitive to that resource; check the enemy-effectiveness result to rule out a dead enemy |
| `baseline_vs_baseline_end_drift` (WARN) | Session-level drift (thermal, cloud neighbour changes) - `rq2/procedure/inflation.py`'s `alpha_drift` (Batch 2) is exactly meant to absorb this |
| enemy effectiveness `status: WARN` | The enemy isn't actually creating interference on this platform/cache config - reconsider enemy buffer size/stride before trusting any `interference_effect` result from the same session |
| platform stability FAIL | vmId or CPU model changed mid-session (VM migrated/resized) - discard the session, it isn't a controlled measurement |

## The workload

`rq2/workload/rt_video.py` is the periodic task (SCHED_FIFO, never
SCHED_DEADLINE - the reservation is external). See
`rq2/workload/README.md` for its own calibrate/run/analyze/replay
commands, useful for local smoke-testing outside the campaign machinery.

## Native enemy programs

```bash
make -C stress
stress/enemy --size-kb <LLC size>       --mode rw --cpu 2   # cache enemy
stress/enemy --size-kb <10 x LLC size>  --mode rw --cpu 2   # memory enemy
```

`configs/campaign_profiling.yaml`/`session_profiling.yaml` resolve
`size_kb: from_platform_llc` against `configs/platform.yaml`'s
`llc_size_kb` automatically (run `tools/platform_info.sh` first).

`stress/victim.c` does a fixed amount of work over a buffer and prints its
elapsed time in ms; `stress/enemy_effectiveness.sh` runs it alone and with
enemies running (cache victim vs. cache enemy, memory victim vs. memory
enemy, matched buffer sizes) to prove the enemies actually create
interference, independent of the video workload:

```bash
stress/enemy_effectiveness.sh --victim stress/victim --enemy stress/enemy \
    --victim-cpu 1 --enemy-cpus 2,3 --cache-size-kb <LLC> --memory-size-kb <10xLLC> \
    --output results/derived/enemy_effectiveness/raw.csv
```

The raw per-trial CSV it writes is analyzed in Python
(`rq2.orchestration.checks.enemy_effectiveness_summary`: percentiles with a
distribution-free confidence interval, slowdown ratio, PASS/WARN) - see
`session.py`, which runs this automatically once per session.

## Pod template

`templates/pod_template.yaml` follows the real KubeDeadline manifest
pattern used elsewhere in this repo (see
`research-questions/RQ1_final/kubedeadline-experiments/generate_yaml.py`
and `models/*/generated/*.yaml`): a `RtClaimParameters` +
`ResourceClaimTemplate` pair (`rt.resource.example.com/v1alpha1`,
`resource.k8s.io/v1alpha2`), with the Pod consuming it via
`resourceClaims`/`resources.claims`. It is still **not verified against a
real RQ2 deploy** - namespace, node label and image are copied from that
convention, not confirmed for this workload. `pod_gen.py` only does
placeholder substitution (`{{NAME}} {{CPUS}} {{Q_US}} {{T_US}} {{ARGS}}
{{RESULTS_DIR}}`); ask before rendering pods for a real run.
