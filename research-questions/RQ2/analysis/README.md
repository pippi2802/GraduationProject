# Analysis

Turns `workload/`'s CSV traces (and `stress/`'s raw CSVs) into numbers and
plots. No shared "package" — these are plain sibling scripts, run directly.

- `metrics.py` — sequence metrics shared by `analyze.py` and `replay.py`:
  worst-case `(m,k)`, max consecutive misses, burstiness. Never mix
  instances/CSVs before computing these — they're defined over one task's
  own job order.
- `analyze.py` — per-instance + aggregated timing report from `rt_video.py`
  CSV logs (response time, miss rate, `(m,k)`, `cpu_ns` percentiles, wait
  time, steal time).
- `replay.py` — replays a measured `cpu_ns` trace under a hard CBS budget
  `Q`, for a range of candidate `Q`, to build a budget-risk curve (miss
  rate vs. bandwidth) and pick the smallest `Q` meeting a target tolerance.

## Usage

```bash
python3 analyze.py ../results/*.csv --meta ../results/*.meta.json \
    --output ../results/analysis.json
python3 analyze.py --selftest

python3 replay.py ../results/single_core_instance0.csv --period-ms 41.667 \
    --q-min-ms 5 --q-max-ms 40 --q-steps 30 \
    --output ../results/replay.csv --plot ../results/replay.png \
    --target-miss-rate 0.01 --max-consecutive 3 --mk 48,50
python3 replay.py --selftest
```
