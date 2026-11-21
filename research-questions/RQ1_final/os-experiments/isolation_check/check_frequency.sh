#!/usr/bin/env bash
# check_frequency.sh <namespace> <label> <cpu> [phase_secs=40]
#
# Does the frequency setting do anything on this VM? Through the rq1-agent (nsenter into the host).
# 1. Static: cpufreq driver, governor, turbo, reported MHz, cpuinfo flags (constant_tsc, aperfmperf), perf cycles available?, steal.
# 2. Speed test: fixed amount of pure-integer work (Python loop), pinned to <cpu>, repeated for the whole phase; prints median/p99/cv
#    of one repetition and the median per 10 s bucket (drift). Phases: (A) as configured, (B) governor powersave + turbo allowed (if the
#    guest lets you write them), (C) back to the original. If the guest setting really controls the clock, B should be slower than A;
#    if A == B within noise, the setting has no effect on the hardware here. All settings are restored at the end.
# Run on an otherwise idle node (no workload pod). Output also in results/<label>.txt.
set -euo pipefail
NS="${1:?usage: check_frequency.sh <namespace> <label> <cpu> [phase_secs]}"; LABEL="${2:?label}"; CPU="${3:?cpu}"; SECS="${4:-40}"
HERE="$(cd "$(dirname "$0")" && pwd)"; mkdir -p "$HERE/results"
AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}')
kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- bash -s -- "$LABEL" "$CPU" "$SECS" <<'CORE' | tee "$HERE/results/$LABEL.txt"
set -u
LABEL=$1; CPU=$2; SECS=$3
CF=/sys/devices/system/cpu/cpu$CPU/cpufreq
echo "=== $LABEL: static state, cpu$CPU ==="
echo "kernel $(uname -r); hypervisor: $(systemd-detect-virt 2>/dev/null)"
for f in scaling_driver scaling_governor scaling_available_governors scaling_cur_freq scaling_min_freq scaling_max_freq cpuinfo_min_freq cpuinfo_max_freq; do
  printf "%-28s %s\n" "$f" "$(cat $CF/$f 2>/dev/null || echo '(not exposed)')"; done
echo "no_turbo (intel_pstate): $(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || echo '(not exposed)')   boost: $(cat /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || echo '(not exposed)')"
echo "model: $(awk -F: '/model name/{print $2; exit}' /proc/cpuinfo)"
echo "cpu MHz per cpu: $(awk -F: '/cpu MHz/{printf "%s ", $2}' /proc/cpuinfo)"
echo "flags of interest: $(grep -m1 '^flags' /proc/cpuinfo | tr ' ' '\n' | grep -E '^(constant_tsc|nonstop_tsc|tsc_reliable|aperfmperf|hypervisor|tsc_known_freq)$' | tr '\n' ' ')"
echo "msr module/device: $(ls /dev/cpu/$CPU/msr 2>/dev/null || echo 'no /dev/cpu/N/msr')"
if command -v perf >/dev/null; then echo "perf cycles: $(perf stat -e cycles -x, -- true 2>&1 | head -1)"; else echo "perf: not installed"; fi
echo "steal (cpu line, /proc/stat): $(awk '/^cpu'$CPU' /{print $9}' /proc/stat) jiffies"

bench() {  # <phase label> <seconds>
python3 - "$CPU" "$1" "$2" <<'PY'
import os, sys, time, statistics
cpu, label, secs = int(sys.argv[1]), sys.argv[2], float(sys.argv[3])
os.sched_setaffinity(0, {cpu})
def work():
    x = 0
    for i in range(400000):
        x = (x * 31 + i) & 0xffffffff
    return x
work()
t_end = time.perf_counter() + secs; t0 = time.perf_counter()
reps = []; buckets = {}
while time.perf_counter() < t_end:
    a = time.perf_counter_ns(); work(); d = (time.perf_counter_ns() - a) / 1e3     # us
    reps.append(d); buckets.setdefault(int((time.perf_counter() - t0) // 10), []).append(d)
reps.sort(); n = len(reps)
med = statistics.median(reps); p99 = reps[int(0.99 * (n - 1))]
print(f"  {label:<34} reps={n:6d}  median={med:9.1f} us  p99={p99:9.1f} us  cv={statistics.pstdev(reps)/statistics.mean(reps):.4f}  per-10s median: " +
      " ".join(f"{statistics.median(v):.0f}" for k, v in sorted(buckets.items())))
PY
}

echo; echo "=== $LABEL: speed test, fixed work, ${SECS}s per phase (us per repetition; lower = faster) ==="
G0=$(cat $CF/scaling_governor 2>/dev/null || true); NT0=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true); BO0=$(cat /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || true)
bench "A configured (gov=${G0:-?})" "$SECS"
if [ -w "$CF/scaling_governor" ]; then
  echo powersave > "$CF/scaling_governor" 2>/dev/null; [ -n "$NT0" ] && echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null
  [ -n "$BO0" ] && echo 1 > /sys/devices/system/cpu/cpufreq/boost 2>/dev/null
  echo "  (set governor=$(cat $CF/scaling_governor), no_turbo=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || echo n/a), boost=$(cat /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || echo n/a); reported cur_freq=$(cat $CF/scaling_cur_freq 2>/dev/null || echo n/a))"
  bench "B powersave, turbo allowed" "$SECS"
  echo "$G0" > "$CF/scaling_governor" 2>/dev/null; [ -n "$NT0" ] && echo "$NT0" > /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null
  [ -n "$BO0" ] && echo "$BO0" > /sys/devices/system/cpu/cpufreq/boost 2>/dev/null
  bench "C restored (gov=$(cat $CF/scaling_governor 2>/dev/null))" "$SECS"
else
  echo "  governor not writable here: phase B skipped (the guest cannot change anything)"
fi
echo "steal after: $(awk '/^cpu'$CPU' /{print $9}' /proc/stat) jiffies"
CORE
