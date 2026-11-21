#!/usr/bin/env bash
# check_isolation.sh <namespace> <label> <rt_cpus> [secs=40] [mode=task|idle]
#
# Direct validation of the isolation on the node: interrupts per second on the RT core(s) during a window.
# Runs from the control machine through the rq1-agent pod (nsenter into the host), like verify_scenario.sh.
#   mode=idle : no task, window starts immediately.
#   mode=task : waits until the `workload` process runs (start run_job.sh for ONE utilization in another terminal), skips WARM s of
#               calibration/start-up, then measures. nohz_full only stops the tick while ONE task runs on the core.
# Before/after: /proc/interrupts (all lines: LOC timer, HVS Hyper-V synthetic timer, HYP hypervisor callback, RES, CAL, TLB, ...).
# During: `ps -eLo psr,comm` for the RT cores, sampled every 2 s (what else runs there).
# Once: boot state (isolated, nohz_full, cmdline), IRQ affinities, rcuo* threads' Cpus_allowed_list.
# Output: stdout and results/<label>.txt next to this script.
set -euo pipefail
NS="${1:?usage: check_isolation.sh <namespace> <label> <rt_cpus e.g. 1 or 1,2,3> [secs] [task|idle]}"
LABEL="${2:?label}"; RT="${3:?rt cpus}"; SECS="${4:-40}"; MODE="${5:-task}"; WARM=${WARM:-15}
HERE="$(cd "$(dirname "$0")" && pwd)"; mkdir -p "$HERE/results"
AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}')
echo "[check] ns=$NS agent=$AGENT label=$LABEL rt=$RT secs=$SECS mode=$MODE" >&2

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$LABEL" "$RT" "$SECS" "$MODE" "$WARM" <<'CORE' | tee "$HERE/results/$LABEL.txt"
set -u
LABEL=$1; RT=$2; SECS=$3; MODE=$4; WARM=$5
expand() { echo "$1" | tr ',' '\n' | while read -r a; do case "$a" in *-*) seq "${a%-*}" "${a#*-}";; *) echo "$a";; esac; done; }
CPUS=$(expand "$RT" | sort -n | tr '\n' ' ')
snap() { awk -v cpus="$CPUS" 'BEGIN{n=split(cpus,c," ")}
  NR==1{next} { name=$1; sub(":","",name); lab=$NF; if ($0 ~ /Local timer/) lab="LOC"; for(i=1;i<=n;i++){ v=$(c[i]+2); if (v ~ /^[0-9]+$/) print name"|"c[i]"|"v } }' /proc/interrupts; }

echo "=== $LABEL: boot state ==="
echo "cmdline: $(cat /proc/cmdline)"
echo "isolated: [$(cat /sys/devices/system/cpu/isolated)]  nohz_full: [$(cat /sys/devices/system/cpu/nohz_full)]  SMT: $(cat /sys/devices/system/cpu/smt/control 2>/dev/null)  kernel: $(uname -r)  CONFIG_HZ: $(grep -h '^CONFIG_HZ=' /boot/config-$(uname -r) 2>/dev/null)"
echo "governor cpu1: $(cat /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor 2>/dev/null)"
echo "--- IRQ affinity (distinct smp_affinity_list over /proc/irq/*) ---"
cat /proc/irq/*/smp_affinity_list 2>/dev/null | sort | uniq -c | sort -rn
echo "--- rcuo* threads: Cpus_allowed_list ---"
for p in $(pgrep '^rcuo' || true); do echo "$(cat /proc/$p/comm) $(awk '/Cpus_allowed_list/{print $2}' /proc/$p/status)"; done | awk '{c[$2]++} END{for(k in c) print c[k]" threads allowed on "k}'

if [ "$MODE" = task ]; then
  echo "[wait] for the workload process ..." >&2
  until pgrep -x workload >/dev/null; do sleep 1; done
  echo "[wait] workload up; warm-up ${WARM}s" >&2; sleep "$WARM"
  echo "workload threads: $(ps -eLo psr,comm,pid | awk '$2=="workload"{print "cpu"$1}' | sort | uniq -c | tr '\n' ' ')"
fi

snap > /tmp/irq_before.$$; t0=$(date +%s.%N); : > /tmp/ps_samples.$$
end=$(( $(date +%s) + SECS ))
while [ "$(date +%s)" -lt "$end" ]; do
  ps -eLo psr,comm,pid | awk -v cpus="$CPUS" 'BEGIN{n=split(cpus,c," "); for(i=1;i<=n;i++) w[c[i]]=1} $1 in w{print "cpu"$1" "$2}' >> /tmp/ps_samples.$$
  sleep 2
done
snap > /tmp/irq_after.$$; t1=$(date +%s.%N)
DT=$(echo "$t1 - $t0" | bc)

echo; echo "=== $LABEL: interrupts per second on the RT cores over ${DT}s (window ${SECS}s, mode=$MODE) ==="
printf "%-10s %-5s %12s %10s\n" irq cpu delta per_s
join -t'|' -j1 <(awk -F'|' '{print $1"/"$2"|"$3}' /tmp/irq_before.$$ | sort -t'|' -k1,1) <(awk -F'|' '{print $1"/"$2"|"$3}' /tmp/irq_after.$$ | sort -t'|' -k1,1) \
 | awk -F'|' -v dt="$DT" '{d=$3-$2; if (d>0) {split($1,a,"/"); printf "%-10s cpu%-2s %12d %10.2f\n", a[1], a[2], d, d/dt}}' | sort -k2,2 -k3,3nr
echo "(only lines with delta > 0 are listed; LOC = local timer, HVS = Hyper-V synthetic timer, HYP = hypervisor callback, RES = reschedule IPI, CAL = function call IPI)"
echo; echo "=== threads seen on the RT cores (ps -eLo psr,comm, every 2 s; count = samples) ==="
sort /tmp/ps_samples.$$ | uniq -c | sort -k2,2 -k1,1nr
rm -f /tmp/irq_before.$$ /tmp/irq_after.$$ /tmp/ps_samples.$$
CORE
