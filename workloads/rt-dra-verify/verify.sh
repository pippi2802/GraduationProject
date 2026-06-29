#!/usr/bin/env bash
#
# RT-DRA verification probe
# -------------------------
# A tiny, dependency-free workload that checks whether the behaviour described
# in the KubeDeadline paper is actually observable on this node:
#
#   1. SCHEDULER   - can a task run under SCHED_FIFO/RR (i.e. is RT bandwidth
#                    available to this cgroup)?  Reports the live policy.
#   2. PARAMETERS  - does the cgroup carry the runtime/period budget that the
#                    RtClaimParameters / CDI env say it should?
#   3. BEHAVIOUR   - run a small periodic task under that policy and measure
#                    wake-up lateness, so you can *see* it behaving like an RT
#                    task (low, bounded jitter) rather than a CFS task.
#   4. GROUP/CBS   - look for evidence at the *cgroup* (SCHED_DEADLINE server)
#                    level: dump dl_rq and run a SCHED_FIFO busy loop to see if
#                    it is throttled to ~ rt_runtime/rt_period (CBS enforcing)
#                    vs. consuming ~100% of a CPU (no group-level enforcement).
#                    NOTE: the tasks inside run SCHED_FIFO; the *group* is the
#                    deadline server -- this is the half sections [4]/[5] miss.
#
# It is intentionally observational: it does NOT assert hard real-time
# guarantees, it just makes the scheduler/parameters/behaviour visible so you
# can compare against the paper.
#
# Runs fine with no special tooling: only bash + coreutils + util-linux
# (chrt/taskset), all present in ubuntu:22.04. No network access required.
#
# Tunables (env):
#   RT_PROBE_PERIOD_MS  period of the probe loop in ms        (default 100)
#   RT_PROBE_ITERS      number of periods to measure          (default 50)
#   RT_PROBE_PRIO       SCHED_FIFO priority to request        (default 90)
#   RT_PROBE_KEEPALIVE  seconds to sleep at the end (0 = exit) (default 86400)
#   RT_PROBE_THROTTLE_SECS  window for the group throttling test (default 3)

set -u

PERIOD_MS="${RT_PROBE_PERIOD_MS:-100}"
ITERS="${RT_PROBE_ITERS:-50}"
FIFO_PRIO="${RT_PROBE_PRIO:-90}"
KEEPALIVE="${RT_PROBE_KEEPALIVE:-86400}"

hr()  { printf -- '------------------------------------------------------------\n'; }
log() { printf '%s\n' "$*"; }

# Map the numeric policy from /proc/<pid>/stat field 41 to a name.
policy_name() {
  case "${1:-}" in
    0) echo "SCHED_OTHER (CFS)";;
    1) echo "SCHED_FIFO (RT)";;
    2) echo "SCHED_RR (RT)";;
    3) echo "SCHED_BATCH";;
    5) echo "SCHED_IDLE";;
    6) echo "SCHED_DEADLINE";;
    *) echo "UNKNOWN(${1:-?})";;
  esac
}

# Read the running scheduler policy + rt priority of a pid from /proc.
report_sched() {
  local who="$1" pid="$2" pol prio
  # field 18 = priority, field 40 = rt_priority, field 41 = policy
  read -r pol prio < <(awk '{print $41, $40}' "/proc/${pid}/stat" 2>/dev/null)
  log "  ${who}: policy=$(policy_name "${pol}") rt_priority=${prio:-?} (pid ${pid})"
}

# ---------------------------------------------------------------------------
# --probe mode: the periodic measurement loop. Invoked as a child so it can be
# wrapped in chrt without affecting the reporting shell.
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--probe" ]; then
  period_ns=$(( PERIOD_MS * 1000000 ))
  min="" ; max="" ; sum=0
  start=$(date +%s%N)
  for (( i=1; i<=ITERS; i++ )); do
    target=$(( start + i * period_ns ))
    now=$(date +%s%N)
    rem=$(( target - now ))
    if (( rem > 0 )); then
      sleep "$(awk -v n="$rem" 'BEGIN{printf "%.9f", n/1e9}')"
    fi
    now=$(date +%s%N)
    late=$(( now - target ))
    (( late < 0 )) && late=$(( -late ))
    sum=$(( sum + late ))
    if [ -z "$min" ]; then min=$late; max=$late; fi
    (( late < min )) && min=$late
    (( late > max )) && max=$late
  done
  avg=$(( sum / ITERS ))
  # field 41 = policy of THIS probe process
  ppol=$(awk '{print $41}' /proc/self/stat 2>/dev/null)
  log "  probe ran as: $(policy_name "${ppol}")"
  awk -v mn="$min" -v av="$avg" -v mx="$max" 'BEGIN{
    printf "  wake-up lateness (us): min=%.1f  avg=%.1f  max=%.1f  jitter(max-min)=%.1f\n",
           mn/1000, av/1000, mx/1000, (mx-mn)/1000
  }'
  exit 0
fi

# ---------------------------------------------------------------------------
# Main report
# ---------------------------------------------------------------------------
hr
log "RT-DRA VERIFICATION PROBE"
log "node=$(uname -n)  kernel=$(uname -r)"
hr

# --- 1. CDI / claim parameters injected by the driver ----------------------
# Show only driver-injected vars (RT_RUNTIME_PERIOD, RT_CPUSET, DRA_*); exclude
# this probe's own RT_PROBE_* tunables.
log "[1] Injected RT-DRA parameters (from CDI / ResourceClaim):"
if env | grep -E '^(RT_|DRA_)' | grep -qvE '^RT_PROBE_'; then
  env | grep -E '^(RT_|DRA_)' | grep -vE '^RT_PROBE_' | sed 's/^/  /'
else
  log "  (no CDI RT_* env injected -- pod may not have an RT ResourceClaim)"
fi
hr

# --- 2. cgroup RT budget on this node --------------------------------------
log "[2] cgroup RT budget visible to this container (cgroup v2):"
cg=/sys/fs/cgroup
for f in cpu.rt_period_us cpu.rt_runtime_us cpu.rt_multi_runtime_us; do
  if [ -r "${cg}/${f}" ]; then
    log "  ${f} = $(cat "${cg}/${f}" 2>/dev/null)"
  else
    log "  ${f} = (absent)"
  fi
done
log "  cgroup path: $(cat /proc/self/cgroup 2>/dev/null | sed 's/^/    /')"
hr

# --- 3. CPU affinity (cpuset from the claim) -------------------------------
log "[3] CPU affinity (cpuset pinned by RT-DRA):"
if command -v taskset >/dev/null 2>&1; then
  taskset -cp "$$" 2>/dev/null | sed 's/^/  /'
else
  log "  taskset not available"
fi
hr

# --- 4. Scheduler check: can we run as SCHED_FIFO? -------------------------
log "[4] Scheduler check (KubeDeadline expects RT tasks under SCHED_FIFO/RR):"
report_sched "shell (before)" "$$"
RT_OK=0
chrt_err=""
if command -v chrt >/dev/null 2>&1; then
  if chrt -f "$FIFO_PRIO" true 2>/tmp/chrt.err; then
    RT_OK=1
  else
    chrt_err="$(cat /tmp/chrt.err 2>/dev/null)"
  fi
else
  chrt_err="chrt not available"
fi
if [ "$RT_OK" = 1 ]; then
  log "  -> CAN run under SCHED_FIFO prio ${FIFO_PRIO}  (RT bandwidth IS available)"
else
  log "  -> CANNOT run under SCHED_FIFO  (${chrt_err:-permission/budget denied})"
  log "     This is the KubeDeadline failure mode: no RT budget => RT tasks denied."
fi
hr

# --- 5. Behaviour: periodic probe under the achievable policy --------------
log "[5] Periodic behaviour (${ITERS} periods of ${PERIOD_MS} ms):"
if [ "$RT_OK" = 1 ]; then
  chrt -f "$FIFO_PRIO" bash "$0" --probe
else
  log "  (running probe under SCHED_OTHER -- baseline, expect higher jitter)"
  bash "$0" --probe
fi
hr

# --- 6. Group-level SCHED_DEADLINE / CBS enforcement evidence ---------------
# In the HCBS model the CONTAINER CGROUP is the SCHED_DEADLINE/CBS *server*,
# while the tasks inside it run SCHED_FIFO/RR and consume the server's reserved
# bandwidth (Q,P). Sections [4]/[5] above prove the *task* side (FIFO); this
# section looks for evidence at the *group* (deadline server) side.
log "[6] Group-level SCHED_DEADLINE / CBS enforcement (the cgroup is the server):"
GROUP_VERDICT="n/a (skipped)"

# 6a. dl_rq snapshot: a deadline runqueue with non-zero dl bandwidth / running
# count is direct evidence that a SCHED_DEADLINE server is active on this node.
DBG=/sys/kernel/debug/sched/debug
if [ -r "$DBG" ]; then
  log "  dl_rq snapshot (from ${DBG}):"
  if grep -E 'dl_rq|dl_nr_running|dl_bw|\.dl_' "$DBG" 2>/dev/null | head -n 20 | sed 's/^/    /' | grep -q .; then
    grep -E 'dl_rq|dl_nr_running|dl_bw|\.dl_' "$DBG" 2>/dev/null | head -n 20 | sed 's/^/    /'
  else
    log "    (no dl_rq lines found)"
  fi
else
  log "  ${DBG} not readable (needs privileged + debugfs mounted) -- skipping dl_rq dump"
fi

# 6b. Behavioural throttling test. A SCHED_FIFO busy loop pinned to one CPU
# should be throttled to ~ rt_runtime/rt_period of that CPU if the CBS server
# enforces the budget; otherwise it consumes ~100% (capped only by the global
# kernel RT throttle, ~95%).
RUNTIME_US=$(cat "${cg}/cpu.rt_runtime_us" 2>/dev/null || echo 0)
PERIOD_US=$(cat "${cg}/cpu.rt_period_us" 2>/dev/null || echo 0)
WINDOW="${RT_PROBE_THROTTLE_SECS:-3}"

if [ "$RT_OK" = 1 ] && [ "${PERIOD_US:-0}" -gt 0 ] 2>/dev/null; then
  if [ "${RUNTIME_US:-0}" -gt 0 ] 2>/dev/null; then
    exp_pct=$(awk -v r="$RUNTIME_US" -v p="$PERIOD_US" 'BEGIN{printf "%.1f", (r/p)*100}')
  else
    exp_pct="?"
  fi
  CLK=$(getconf CLK_TCK 2>/dev/null || echo 100)

  # first CPU of our affinity mask
  cpu0=$(taskset -cp "$$" 2>/dev/null | awk -F': ' '{print $2}' | tr ',' '\n' | head -n1 | cut -d- -f1)
  cpu0="${cpu0:-0}"

  # launch a pure-CPU SCHED_FIFO loop on that CPU (exec chain keeps one PID)
  chrt -f "$FIFO_PRIO" taskset -c "$cpu0" bash -c 'while :; do :; done' &
  burn_pid=$!

  # measure CPU time (utime+stime, fields 14+15) consumed over the window
  c0=$(awk '{print $14+$15}' "/proc/${burn_pid}/stat" 2>/dev/null || echo 0)
  t0=$(date +%s%N)
  sleep "$WINDOW"
  c1=$(awk '{print $14+$15}' "/proc/${burn_pid}/stat" 2>/dev/null || echo 0)
  t1=$(date +%s%N)
  kill -9 "$burn_pid" 2>/dev/null
  wait "$burn_pid" 2>/dev/null

  cpu_ticks=$(( c1 - c0 ))
  wall_ns=$(( t1 - t0 ))
  obs_pct=$(awk -v ct="$cpu_ticks" -v clk="$CLK" -v wn="$wall_ns" \
              'BEGIN{ if(wn>0) printf "%.1f", (ct/clk)/(wn/1e9)*100; else printf "0.0" }')

  log "  SCHED_FIFO busy-loop on CPU ${cpu0} for ${WINDOW}s:"
  log "    expected CPU share (rt_runtime/rt_period) : ${exp_pct}%"
  log "    observed CPU share                        : ${obs_pct}%"

  is_throttled=$(awk -v o="$obs_pct" -v e="$exp_pct" 'BEGIN{
    if (e=="?") { print "unknown"; exit }
    if (o+0 >= 90.0) { print "no"; exit }
    if ((e+0) > 0 && o+0 <= (e+0)*1.5 + 5) { print "yes"; exit }
    print "partial"
  }')
  case "$is_throttled" in
    yes)     GROUP_VERDICT="THROTTLED -> CBS/SCHED_DEADLINE ENFORCING (obs=${obs_pct}% ~ exp=${exp_pct}%)";;
    no)      GROUP_VERDICT="NOT enforced (obs=${obs_pct}% ~ full CPU; group is not a CBS server)";;
    partial) GROUP_VERDICT="partial (obs=${obs_pct}% vs exp=${exp_pct}% -- inspect)";;
    *)       GROUP_VERDICT="cannot compare (rt_runtime not set)";;
  esac
  log "    verdict: ${GROUP_VERDICT}"
else
  log "  (skipped throttling test: needs SCHED_FIFO available AND cpu.rt_period_us > 0)"
fi
hr

# --- summary ---------------------------------------------------------------
log "SUMMARY"
log "  scheduler available : $( [ "$RT_OK" = 1 ] && echo 'SCHED_FIFO (RT)  [matches paper]' || echo 'SCHED_OTHER only [RT NOT enforced]' )"
log "  group RT enforcement: ${GROUP_VERDICT}"
log "  rt_runtime_us       : $(cat ${cg}/cpu.rt_runtime_us 2>/dev/null || echo n/a)"
log "  rt_period_us        : $(cat ${cg}/cpu.rt_period_us 2>/dev/null || echo n/a)"
log "  rt_multi_runtime_us : $(cat ${cg}/cpu.rt_multi_runtime_us 2>/dev/null || echo n/a)"
hr

# Keep the pod alive so it can be inspected with `kubectl exec`.
if [ "${KEEPALIVE}" != "0" ]; then
  log "probe complete; sleeping ${KEEPALIVE}s (override with RT_PROBE_KEEPALIVE=0)"
  sleep "${KEEPALIVE}"
fi
