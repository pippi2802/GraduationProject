# Step 1: the platform level (once per VM type, independent of the workload)

Datasets (all measured on the VM type you will deploy on):

| ID | Dataset | Content | Used for |
|---|---|---|---|
| P1 | victim alone | the cache victim and the memory victim, no enemies, `--trials` runs each | denominator of alpha_platform |
| P2 | victim with enemies | both victims with m = 1, 2, 3 enemy cores (the dial), `--trials` runs each | numerator of alpha_platform(m) |
| P3 | noise floor (optional) | the periodic loop with an EMPTY job on an RT core, at the period of your task | the runtime's own overhead and dispatch latency |

## Run (on the VM, from this folder)
```bash
./run_platform.sh --victim-cpu 1 --enemy-cpus "2;2,3;2,3,0" --trials 20                      # P1 + P2
sudo ./run_platform.sh --victim-cpu 1 --enemy-cpus "2;2,3;2,3,0" --noise-period-ms 41.667 --noise-cpu 1   # P1 + P2 + P3 (FIFO needs root)
```
`--enemy-cpus` is the dial: one group per level, separated by `;` (here 1, 2 and 3 enemy cores). Never use a core of the victim. It builds the
tools (`make`; `victim.c`, `enemy.c` and the two scripts are copies of `../../stress1/`), sizes the buffers from the last-level cache (check `lscpu`
on VMs with several L3 instances, or pass `--cache-kb` / `--memory-kb`), and writes the files below. `verify_targets.sh` (a copy) proves each
enemy stresses the mechanism it claims to, with `perf`; run it once before trusting the numbers.

## Results (`results/`)
- `victim_raw.csv`, `victim_summary.csv`: P1 + P2, one row per trial.  `noise_floor/instance0.csv`: P3.
- **`platform_factor.csv`**: m, medians, ratios, `alpha_platform` = the larger of the cache and the memory victim's (median with m enemies / median alone). Read by step 4.
- **`noise_floor_summary.csv`**: overhead (CPU time of the empty job) and dispatch latency in microseconds. Read by step 4, which compares them with your task.

`python3 compute_platform.py` recomputes both from the raw files.
