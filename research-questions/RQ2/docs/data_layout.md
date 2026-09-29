# Results layout and schemas

```
results/
  raw/<session>/<deployment>/<condition>/<run_id>/
    <instance_id>.csv          rt_video.py trace (see schema below)
    <instance_id>.meta.json    rt_video.py run metadata
    pod_<instance_id>.yaml     rendered pod spec used for this run (orchestration only)
    manifest.json              one manifest per run_id (see schema below)
  raw/<session>/campaign.log   campaign.py's log for that session
  derived/<stage>/...          JSON/CSV summaries produced by rq2/procedure, rq2/validation
  figures/                     PDF + PNG, from rq2/reporting/figures.py
  tables/                      LaTeX (booktabs), from rq2/reporting/tables.py
```

`<session>` is a campaign run (e.g. `profiling_v1`), `<deployment>` is
`single_core`/`multi_core`, `<condition>` names a profiling condition
(`baseline`, `cache_enemy_dial1`, `hk_loaded`, ...) or a validation
condition (`<variant>_p<p>_stress-<on|off>`), `<run_id>` is `session0`,
`session1`, ... (one per repetition in `sessions_per_condition`).

## `<instance_id>.csv` (written by `rq2/workload/rt_video.py`)

One row per activation, including skipped ones.

| column | meaning |
| --- | --- |
| `instance_id` | task instance name |
| `job_id` | activation index, 0-based |
| `frame_idx` | which preloaded frame this job processed |
| `release_ns` | absolute CLOCK_MONOTONIC release time |
| `start_ns` / `end_ns` | job body start/end (empty if skipped) |
| `cpu_ns` | CPU time of the job body (`time.thread_time_ns`), empty if skipped |
| `response_ns` | `end_ns - release_ns` |
| `wait_ns` | `start_ns - release_ns` |
| `lateness_ns` | `end_ns - (release_ns + deadline_ns)` |
| `deadline_met` | 0/1 |
| `skipped` | 0/1 (overrun=skip: this activation was skipped) |
| `warmup` | 0/1 - excluded from every analysis stage |

## `<instance_id>.meta.json`

CLI args, instance id, start time (UTC), hostname, kernel version, CPU
model, threads/core, cpu count, `/proc/stat` `cpu` line at start and end
(steal time), whether mlockall/SCHED_FIFO/affinity succeeded, and
Python/OpenCV/NumPy versions. See `rq2/workload/rt_video.py:write_metadata`.

## `manifest.json` (written by `rq2/common/manifest.py`)

```json
{
  "status": "running | complete | failed",
  "config": { ... the run spec campaign.py built for this run ... },
  "command": ["campaign.py"],
  "git_commit": "abcdef...",
  "hostname": "...",
  "user": "...",
  "python_version": "...",
  "start_time_utc": "2026-09-28T12:00:00+00:00",
  "end_time_utc": "2026-09-28T12:05:00+00:00"
}
```

`campaign.py` treats a run as done and skips it (resumability) iff
`manifest.json` exists with `status == "complete"`.

## `results/derived/budget/budgets.json` (Batch 2, `rq2/procedure/budget.py`)

Contract consumed by `rq2/orchestration/pod_gen.py` in validation mode:

```json
{
  "<deployment>": {
    "<instance_id>": {
      "<variant>": {
        "<p as string, e.g. \"0.01\">": {
          "q_us": 12345.0,
          "t_us": 33300.0,
          "route": "direct | reuse",
          "admission_ok": true
        }
      }
    }
  }
}
```

## `results/derived/platform/platform_info.json` (`tools/platform_info.sh`)

CPU model, threads/core, kernel version + cmdline, LLC size (KB), full
`lscpu --json` output, and Azure instance metadata if reachable.

Other `results/derived/<stage>/` schemas (tail estimation, inflation,
validation) are documented in each Batch 2/3 module's docstring and
finalized here once those batches land.
