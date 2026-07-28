#!/usr/bin/env bash
# =============================================================================
# Model 1_1 node-prep: detect hyper-thread sibling pairs, pick ONE logical CPU
# per physical core for (RT-under-test, canary), and record the mapping.
#
# DETECT-ONLY by default (DRY_RUN=1): offlining a vCPU on Azure D4s_v5 is
# effectively one-way and WEDGES the VM (and zeroes the RT cgroup budget chain),
# so we do NOT offline. The harness guarantees isolation by placement-retry
# instead (keeps the RT cell off the canary's real SMT sibling). Set DRY_RUN=0
# ONLY on hardware where vCPU hotplug is reversible.
#
# Env: RT_CORE_LOGICAL, CANARY_CORE_LOGICAL, MAP_OUT, DRY_RUN (default 1).
# =============================================================================
set -euo pipefail
SYS=/sys/devices/system/cpu
MAP_OUT="${MAP_OUT:-/var/lib/model1_1/cpu-map.json}"
DRY_RUN="${DRY_RUN:-1}"

die() { echo "FATAL: $*" >&2; exit 1; }
log() { echo "[node-prep] $*" >&2; }
[[ -d "$SYS" ]] || die "$SYS not present"

declare -A SIBLINGS_OF
online_cpus=()
for d in "$SYS"/cpu[0-9]*; do
  cpu="${d##*/cpu}"
  if [[ -f "$d/online" ]] && [[ "$(cat "$d/online")" == "0" ]]; then continue; fi
  tsl="$d/topology/thread_siblings_list"
  [[ -r "$tsl" ]] || die "cannot read $tsl"
  raw="$(cat "$tsl")"
  sibs=(); IFS=',' read -ra parts <<< "$raw"
  for p in "${parts[@]}"; do
    if [[ "$p" == *-* ]]; then a="${p%-*}"; b="${p#*-}"; for ((i=a;i<=b;i++)); do sibs+=("$i"); done
    else sibs+=("$p"); fi
  done
  SIBLINGS_OF["${sibs[0]}"]="${sibs[*]}"
  online_cpus+=("$cpu")
done
[[ ${#online_cpus[@]} -gt 0 ]] || die "no online CPUs with readable topology"

mapfile -t core_keys < <(printf '%s\n' "${!SIBLINGS_OF[@]}" | sort -n)
log "detected ${#core_keys[@]} physical core group(s):"
for k in "${core_keys[@]}"; do log "  core[$k]: siblings = ${SIBLINGS_OF[$k]}"; done
[[ ${#core_keys[@]} -ge 2 ]] || die "need >= 2 physical cores; found ${#core_keys[@]}"

read -ra sibs_a <<< "${SIBLINGS_OF[${core_keys[0]}]}"
read -ra sibs_b <<< "${SIBLINGS_OF[${core_keys[1]}]}"
rt_cpu="${RT_CORE_LOGICAL:-${sibs_a[0]}}"
canary_cpu="${CANARY_CORE_LOGICAL:-${sibs_b[0]}}"

offline=()
for c in "${sibs_a[@]}"; do [[ "$c" != "$rt_cpu" ]] && offline+=("$c"); done
for c in "${sibs_b[@]}"; do [[ "$c" != "$canary_cpu" ]] && offline+=("$c"); done
log "RT -> cpu$rt_cpu (core ${core_keys[0]}) ; canary -> cpu$canary_cpu (core ${core_keys[1]})"
log "sibling(s) that WOULD be offlined -> ${offline[*]:-<none>}"

if [[ "$DRY_RUN" != "1" ]]; then
  for c in "${offline[@]}"; do
    f="$SYS/cpu$c/online"
    [[ -w "$f" ]] || die "cannot write $f (need privileged)"
    [[ "$(cat "$f")" == "0" ]] && log "cpu$c already offline" || { echo 0 > "$f"; log "cpu$c set offline"; }
  done
else
  log "DRY_RUN=1: not modifying CPU online state (Azure-safe)"
fi

# ---------------------------------------------------------------------------
# CPU frequency pinning: make calibration-time C match run-time C. If the guest
# lets us, set the performance governor on every online CPU and disable turbo so
# the matmul probe runs at a FIXED frequency in BOTH calibration and the measured
# run. Without this, calibration on an isolated/turbo core UNDERSHOOTS K and the
# real run's C then exceeds Q -> reservation overload and R divergence (observed
# in tb-20260714-1449). Azure guests often restrict cpufreq; this is BEST-EFFORT
# and never fatal. Set PIN_FREQ=0 to leave scaling untouched.
# ---------------------------------------------------------------------------
PIN_FREQ="${PIN_FREQ:-1}"
freq_governor="unknown"; turbo_state="unknown"
if [[ "$PIN_FREQ" == "1" ]]; then
  for g in "$SYS"/cpu[0-9]*/cpufreq/scaling_governor; do
    [[ -w "$g" ]] || continue
    avail="${g%scaling_governor}scaling_available_governors"
    if grep -qw performance "$avail" 2>/dev/null && echo performance > "$g" 2>/dev/null; then
      freq_governor="performance"
    fi
  done
  if [[ -w /sys/devices/system/cpu/intel_pstate/no_turbo ]] \
     && echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null; then
    turbo_state="disabled"
  elif [[ -w /sys/devices/system/cpu/cpufreq/boost ]] \
     && echo 0 > /sys/devices/system/cpu/cpufreq/boost 2>/dev/null; then
    turbo_state="disabled"
  fi
  log "freq pin: governor=$freq_governor turbo=$turbo_state"
else
  log "PIN_FREQ=0: leaving CPU frequency scaling as-is"
fi

mkdir -p "$(dirname "$MAP_OUT")"
{
  printf '{\n  "node": "%s",\n  "kernel": "%s",\n' "$(hostname)" "$(uname -r)"
  printf '  "rt_cpu": %s,\n  "canary_cpu": %s,\n' "$rt_cpu" "$canary_cpu"
  if [[ "$DRY_RUN" == "1" ]]; then printf '  "offline_siblings": [],\n'
  else printf '  "offline_siblings": [%s],\n' "$(IFS=,; echo "${offline[*]:-}")"; fi
  printf '  "freq_governor": "%s",\n  "turbo": "%s",\n' "$freq_governor" "$turbo_state"
  printf '  "physical_cores": %s,\n  "dry_run": %s\n}\n' "${#core_keys[@]}" "$DRY_RUN"
} > "$MAP_OUT"
log "wrote CPU map -> $MAP_OUT"; cat "$MAP_OUT" >&2
