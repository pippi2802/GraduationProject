#!/bin/bash
# Samples which cpu each running `workload` process is on (field 39 of
# /proc/<pid>/stat, "processor" = cpu the task last ran on) and reports, per
# process, the cpu histogram and the number of cpu changes (migrations), plus
# the share of samples in which the two processes sit on different cpus.
#
# Run it INSIDE the model5 target pod while a cell is live (the pod only
# exists during a cell; tight scale ~50 s, soft ~500 s):
#
#   kubectl -n <ns> exec -i <pod> -- bash -s -- [duration_s] [interval_s] [name] < check_migration.sh
#
# e.g. kubectl -n m5-phys exec -i model5-phys-tight-u40 -- bash -s -- 30 0.01 < check_migration.sh
#
# Caveat: a periodic task sleeps between jobs, so the sample is the cpu it ran
# on LAST. That is what we want for "where does each task run", but a migration
# that happens and reverts between two samples is not seen (lower the interval).
DUR="${1:-30}"
INT="${2:-0.01}"
NAME="${3:-workload}"

pids=$(pgrep -x "$NAME" | sort -n | tr '\n' ' ')
n=$(wc -w <<<"$pids")
[ "$n" -ge 1 ] || { echo "no '$NAME' process found"; exit 1; }
[ "$n" -ge 2 ] || echo "WARN: only $n '$NAME' process, cross-process stats will be empty"
echo "pids: $pids  affinity: $(taskset -cp "${pids%% *}" 2>/dev/null | sed 's/.*: //')  duration=${DUR}s interval=${INT}s"

end=$((SECONDS + DUR))
tick=0
while [ "$SECONDS" -lt "$end" ]; do
  for p in $pids; do
    if read -r -a f < "/proc/$p/stat" 2>/dev/null; then
      # field 39 = index 38; comm is "(workload)" with no spaces, so no shift
      echo "$tick $p ${f[38]}"
    fi
  done
  tick=$((tick + 1))
  sleep "$INT"
done | awk '
  { s[$1] = s[$1] " " $2 ":" $3; hist[$2, $3]++; pidset[$2] = 1; cnt[$2]++
    if (($2 in last) && last[$2] != $3) mig[$2]++
    last[$2] = $3; cpuset[$3] = 1 }
  END {
    for (p in pidset) {
      printf "pid %s: %d samples, %d cpu changes, cpus:", p, cnt[p], mig[p] + 0
      for (c in cpuset) if ((p, c) in hist) printf " cpu%s=%.1f%%", c, 100 * hist[p, c] / cnt[p]
      printf "\n"
    }
    for (t in s) {
      m = split(s[t], a, " ")
      if (m < 2) continue
      split(a[1], x, ":"); split(a[2], y, ":")
      both++; if (x[2] != y[2]) diff++
    }
    if (both) printf "ticks with both pids seen: %d, on DIFFERENT cpus: %.1f%%, same cpu: %.1f%%\n", both, 100 * diff / both, 100 * (both - diff) / both
  }'
