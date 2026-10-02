# Stress

Two interference generators, pinned to a specific core, run until SIGTERM.
Never run them on a core the workload is using.

- `enemy.c` → `enemy` — cache enemy (`--size-kb <LLC size>`) or memory
  enemy (`--size-kb <10x LLC size>`), same binary, `--mode rw --cpu N`.
- `victim.c` → `victim` — does a FIXED amount of work and prints elapsed
  ms; used to measure how much an enemy slows things down.
- `enemy_effectiveness.sh` — runs the victim alone, then with each enemy,
  in sequence, across one or more DIAL LEVELS (1, 2, 3... competing enemy
  cores); writes a per-trial raw CSV and a one-row-per-dial summary CSV
  (median times, slowdown, avg enemy throughput) ready for a thesis table.
- `verify_targets.sh` — proves each enemy stresses the mechanism it claims
  to (cache-capacity vs. memory-bandwidth), via `perf` hardware counters on
  the enemy's own core. Run this once before trusting `enemy_effectiveness.sh`.

## Build

```bash
make
```

## Get the real LLC size first

```bash
lscpu | grep 'L3 cache'   # or L2 if there's no L3
```

## Run

```bash
# --enemy-cpus takes one or more dial levels separated by ';', each a
# comma-separated cpu list - "2;2,3;2,3,0" runs a 1/2/3-core dial in one go.
# A single group ("2,3") runs just that one dial level.
./enemy_effectiveness.sh --victim ./victim --enemy ./enemy \
    --victim-cpu 1 --enemy-cpus "2;2,3;2,3,0" \
    --cache-size-kb <LLC> --memory-size-kb <10x LLC> \
    --output ../results/enemy_effectiveness_raw.csv \
    --summary-output ../results/enemy_effectiveness_summary.csv

./verify_targets.sh --enemy ./enemy --cpu 2 \
    --cache-size-kb <LLC> --memory-size-kb <10x LLC> \
    --output ../results/verify_targets.csv
```
