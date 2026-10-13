#!/usr/bin/env bash
#
# Live RT-budget rewrite test (run as root ON A WORKER with the HCBS kernel).
#
# Questions answered:
#   Q1  Can cpu.rt_runtime_us of a RUNNING pod's cgroup be rewritten (grow / shrink)?
#   Q2  Does anything (kubelet, containerd, rt-DRA driver, reseed unit) put the old
#       value back? Watched passively for WATCH_SECS, then after a forced kubelet
#       restart.
#   Q3  What happens when the budget is shrunk while the task inside is consuming it
#       (does the task get throttled to the new share, killed, or is the write refused)?
#   Q4  Is shrinking a PARENT below the sum of its children refused (EINVAL)?
#
# Usage:
#   sudo ./budget-rewrite-test.sh <pod-uid-or-name-substring> [cpu]
#
# Prereq: an RT pod (e.g. rt-verify.yaml) already Running on this node with an
# admitted reservation. cpu = the core the reservation lives on (default 0).
#
# Facts used (see setup/scripts/rt-budget-reseed.sh):
#   * cpu.rt_runtime_us WRITE format: "<run> <cpu> <run> <cpu> ..."; READ: "R R R R".
#   * cpu.rt_period_us must be written before cpu.rt_runtime_us.
#   * Sum(children runtime) <= parent per CPU.

set -uo pipefail

PATTERN="${1:?pod uid or name substring}"
CPU="${2:-0}"
WATCH_SECS="${WATCH_SECS:-60}"
CG=/sys/fs/cgroup
OUT="${OUT:-/tmp/budget-rewrite-$(date +%Y%m%d-%H%M%S).log}"

[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }
exec > >(tee -a "$OUT") 2>&1

log() { printf '[%s] %s\n' "$(date +%T)" "$*"; }
rt()  { cat "$1/cpu.rt_runtime_us" 2>/dev/null; }

# --- locate the container leaf cgroup -----------------------------------------
uid_part="${PATTERN//-/_}"
leaf="$(find "$CG/kubepods.slice" -type d -name 'cri-containerd-*.scope' 2>/dev/null |
  while read -r d; do
    case "$d" in *"$PATTERN"*|*"$uid_part"*) echo "$d";; esac
  done | head -1)"
[ -n "$leaf" ] || { echo "no container scope matching '$PATTERN' (pass the pod UID; kubectl get pod -o jsonpath='{.metadata.uid}')"; exit 1; }
podcg="$(dirname "$leaf")"
slice="$(dirname "$podcg")"
log "leaf   = $leaf"
log "podcg  = $podcg"
log "parent = $slice"

PERIOD="$(cat "$leaf/cpu.rt_period_us")"
BASE="$(rt "$leaf")"
log "baseline leaf runtime='$BASE' period=$PERIOD"
[ -n "$BASE" ] || { echo "leaf has no cpu.rt_runtime_us"; exit 1; }

# runtime on $CPU from the READ array
cur() { awk -v c="$CPU" '{print $(c+1)}' "$1/cpu.rt_runtime_us"; }
BASE_CPU="$(cur "$leaf")"
[ "${BASE_CPU:-0}" -gt 0 ] || { echo "leaf runtime on cpu$CPU is 0: pick the right cpu"; exit 1; }

# write "<us> <cpu>" to a cgroup, period first; report rc + readback
setrt() {
  local d="$1" us="$2" p; p="$(cat "$d/cpu.rt_period_us")"
  echo "$p" > "$d/cpu.rt_period_us" 2>/dev/null
  if echo "$us $CPU" > "$d/cpu.rt_runtime_us" 2>/tmp/_err; then
    log "WRITE $us (cpu$CPU) -> OK, readback='$(rt "$d")'"; return 0
  else
    log "WRITE $us (cpu$CPU) -> FAIL: $(cat /tmp/_err); readback='$(rt "$d")'"; return 1
  fi
}

# --- Q1a: grow -----------------------------------------------------------------
log "== Q1a grow: +10% of period"
grow=$(( BASE_CPU + PERIOD / 10 ))
setrt "$leaf" "$grow"
log "   (if FAIL: check parent headroom: pod=$(rt "$podcg") slice=$(rt "$slice"))"
setrt "$leaf" "$BASE_CPU"

# --- Q3: shrink under load -----------------------------------------------------
log "== Q3 shrink while in use: SCHED_FIFO busy loop in the leaf, measure CPU share"
share() {  # CPU seconds consumed by pid over 3s
  local pid="$1" a b
  a=$(awk '{print $14+$15}' /proc/$pid/stat); sleep 3
  b=$(awk '{print $14+$15}' /proc/$pid/stat)
  awk -v a="$a" -v b="$b" -v hz="$(getconf CLK_TCK)" 'BEGIN{printf "%.2f", (b-a)/hz/3}'
}
( echo $BASHPID > "$leaf/cgroup.procs" && exec taskset -c "$CPU" chrt -f 50 sh -c 'while :; do :; done' ) &
spin=$!
sleep 1
if ! grep -q "$(basename "$leaf")" /proc/$spin/cgroup 2>/dev/null; then
  log "spinner did not enter leaf (cgroup.procs write refused?): $(cat /proc/$spin/cgroup 2>&1)"
fi
log "baseline share  (runtime/period=$(awk -v r="$BASE_CPU" -v p="$PERIOD" 'BEGIN{printf "%.2f", r/p}')): $(share $spin)"
half=$(( BASE_CPU / 2 ))
setrt "$leaf" "$half"
log "after shrink to half (expect ~$(awk -v r="$half" -v p="$PERIOD" 'BEGIN{printf "%.2f", r/p}')): $(share $spin)"
log "spinner alive? $(kill -0 $spin 2>/dev/null && echo yes || echo NO-killed)"
setrt "$leaf" 0
log "after shrink to 0 write: share=$(share $spin) alive=$(kill -0 $spin 2>/dev/null && echo yes || echo no)"
setrt "$leaf" "$BASE_CPU"

# --- Q2: does anything revert the value? ---------------------------------------
log "== Q2 reconcile: set leaf to half and watch ${WATCH_SECS}s (passive)"
setrt "$leaf" "$half"
reverted=0
for ((i = 0; i < WATCH_SECS; i++)); do
  v="$(cur "$leaf")"
  if [ "$v" != "$half" ]; then log "REVERTED at t=${i}s -> $v"; reverted=1; break; fi
  sleep 1
done
[ $reverted -eq 0 ] && log "no revert in ${WATCH_SECS}s passive watch"

log "== Q2 forced reconcile: restart kubelet, then re-read"
setrt "$leaf" "$half"
systemctl restart kubelet; sleep 20
log "after kubelet restart: cpu$CPU=$(cur "$leaf") (written $half)"
if systemctl is-enabled rt-budget-reseed.service >/dev/null 2>&1; then
  log "NOTE rt-budget-reseed.service is enabled; it only seeds root/kubepods/besteffort at boot, not pod leaves"
fi

# --- Q3b: kill pod's own process, verify cgroup untouched; restore -------------
setrt "$leaf" "$BASE_CPU"
kill $spin 2>/dev/null; wait $spin 2>/dev/null

# --- Q4: shrink parent below children ------------------------------------------
log "== Q4 shrink pod-level cgroup below its leaf: expect refusal"
PODBASE="$(cur "$podcg")"
log "pod-level cpu$CPU=$PODBASE leaf cpu$CPU=$BASE_CPU"
setrt "$podcg" $(( BASE_CPU / 2 )) && log "!! parent shrink ACCEPTED below child (no hierarchy check)" || log "parent shrink refused (hierarchy enforced)"
setrt "$podcg" "$PODBASE"

log "== done, final leaf='$(rt "$leaf")' (baseline '$BASE'); log: $OUT"
