#!/usr/bin/env bash
# 08_freq_unpinned.sh <namespace> <status|apply|restore>
#
# SUBTRACTIVE: removes just the frequency pin (governor=performance, turbo
# off, min=max freq) from the existing full isolation baseline, leaving
# isolcpus=/nohz_full=/rcu_nocbs=/systemd-containment/IRQ-steering/
# boot-params intact. Requires the baseline to already be applied.
#
# Unlike 01-06, the pin isn't grub-based -- it's set live by the rq1-agent
# DaemonSet's own init container every time it starts (see
# agent-daemonset.yaml.template's SKIP_FREQ_PIN branch). So "removing" it
# here means: (a) redeploy the agent with SKIP_FREQ_PIN=1 so it stops
# RE-pinning on every restart, AND (b) explicitly reset the live sysfs state
# back to its real distro default NOW, since a node that was already pinned
# by a prior scenario's agent won't un-pin itself just because a later
# deploy skips re-pinning it.
set -euo pipefail
NS="${1:?usage: 08_freq_unpinned.sh <namespace> <status|apply|restore>}"
MODE="${2:?usage: 08_freq_unpinned.sh <namespace> <status|apply|restore>}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[08_freq_unpinned] ns=$NS agent=$AGENT mode=$MODE"

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" <<'CORE'
set -u
MODE="$1"

status() {
  echo "--- governor (cpu0) ---"
  cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo "(not exposed)"
  echo "--- available governors ---"
  cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null || echo "(not exposed)"
  echo "--- turbo (intel_pstate no_turbo, 1=off) ---"
  cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || echo "(not exposed)"
  echo "--- boost (cpufreq boost, 1=on) ---"
  cat /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || echo "(not exposed)"
  echo "--- cpu0 min/max freq ---"
  cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq 2>/dev/null || echo "(not exposed)"
  cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || echo "(not exposed)"
}

apply() {
  # pick the real distro default governor -- prefer schedutil, fall back to
  # ondemand, then whatever's first in the available list (never "performance").
  local avail default
  avail=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null || echo "")
  case " $avail " in
    *" schedutil "*) default=schedutil ;;
    *" ondemand "*)  default=ondemand ;;
    *) default=$(echo "$avail" | awk '{print $1}') ;;
  esac
  if [ -z "$default" ]; then
    echo "ERROR: could not determine a default governor from '$avail' -- refusing to guess." >&2
    exit 1
  fi
  for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "$default" > "$g" 2>/dev/null || true
  done
  echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true
  echo 1 > /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || true
  for c in /sys/devices/system/cpu/cpu*/cpufreq; do
    if [ -f "$c/cpuinfo_max_freq" ] && [ -f "$c/scaling_max_freq" ]; then
      cat "$c/cpuinfo_max_freq" > "$c/scaling_max_freq" 2>/dev/null || true
    fi
    if [ -f "$c/cpuinfo_min_freq" ] && [ -f "$c/scaling_min_freq" ]; then
      cat "$c/cpuinfo_min_freq" > "$c/scaling_min_freq" 2>/dev/null || true
    fi
  done
  echo "reset governor to '$default' (real default), turbo/boost re-enabled, min/max freq unpinned."
  echo ">>> Also redeploy this namespace's agent with SKIP_FREQ_PIN=1 (see below) so it doesn't re-pin on its next restart. <<<"
  status
}

restore() {
  for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo performance > "$g" 2>/dev/null || true
  done
  echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true
  echo 0 > /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || true
  for c in /sys/devices/system/cpu/cpu*/cpufreq; do
    if [ -f "$c/scaling_min_freq" ] && [ -f "$c/cpuinfo_min_freq" ]; then
      cat "$c/scaling_min_freq" > "$c/scaling_max_freq" 2>/dev/null || true
    fi
  done
  echo "restored frequency pin (performance/no-turbo/min=max) -- back to full baseline."
  echo ">>> Also redeploy this namespace's agent WITHOUT SKIP_FREQ_PIN so it re-pins on restart. <<<"
  status
}

case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: <status|apply|restore>"; exit 2 ;;
esac
CORE
