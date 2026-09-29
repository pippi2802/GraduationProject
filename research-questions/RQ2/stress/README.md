# Stress

Two interference generators, pinned to a specific core, run until SIGTERM.
Never run them on a core the workload is using.

- `enemy.c` → `enemy` — cache enemy (`--size-kb <LLC size>`) or memory
  enemy (`--size-kb <10x LLC size>`), same binary, `--mode rw --cpu N`.
- `victim.c` → `victim` — does a FIXED amount of work and prints elapsed
  ms; used to measure how much an enemy slows things down.
- `enemy_effectiveness.sh` — runs the victim alone, then with each enemy,
  in sequence; prints a median-based slowdown summary.
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
./enemy_effectiveness.sh --victim ./victim --enemy ./enemy \
    --victim-cpu 1 --enemy-cpus 2,3 \
    --cache-size-kb <LLC> --memory-size-kb <10x LLC> \
    --output ../results/enemy_effectiveness.csv

./verify_targets.sh --enemy ./enemy --cpu 2 \
    --cache-size-kb <LLC> --memory-size-kb <10x LLC> \
    --output ../results/verify_targets.csv
```
