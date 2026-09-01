#!/usr/bin/env bash
# steer-irqs.sh <off|on> <rtcpu>
#
# Runs ON the node, inside the privileged agent. Pipe it in:
#   kubectl -n <ns> exec -i <agent> -- bash -s -- off 2 < node-prep/steer-irqs.sh
#
#   on  : move every steerable device IRQ ONTO the RT core (rtcpu)
#   off : park every steerable device IRQ on a NON-RT core (away from the RT core)
#
# Emits a one-line JSON summary to stdout:
#   mode, rtcpu, park_cpu, steered_ok (accepted), rejected (Azure-managed, refused),
#   irqs_allowed_on_rtcpu (how many IRQ masks still permit the RT core afterwards).
#
# This is the mechanism that makes model4's off/on arms a REAL experiment instead
# of two identical runs. The rejected count directly quantifies the stated Azure
# limitation ("many IRQs are managed and cannot be steered").
set -u
MODE="${1:?usage: steer-irqs.sh <off|on> <rtcpu>}"
RT="${2:?rtcpu required}"

# expand "0-3" / "0,2" cpu lists to a flat space-separated list
expand() { echo "$1" | tr ',' ' ' | while read -r p; do
  case "$p" in *-*) seq "${p%-*}" "${p#*-}" ;; "") ;; *) echo "$p" ;; esac
done | tr '\n' ' '; }

online=$(cat /sys/devices/system/cpu/online 2>/dev/null || echo "0-3")
ALL=$(expand "$online")
rtsibs=$(cat "/sys/devices/system/cpu/cpu$RT/topology/thread_siblings_list" 2>/dev/null || echo "$RT")
RTSET=" $(expand "$(echo "$rtsibs" | tr ',-' '  ')") "   # RT core's logical cpus

# park cpu = first online cpu NOT on the RT core
PARK=""
for c in $ALL; do case "$RTSET" in *" $c "*) ;; *) PARK="$c"; break ;; esac; done
PARK="${PARK:-0}"

if [ "$MODE" = "on" ]; then TARGET="$RT"; else TARGET="$PARK"; fi

steered=0; rejected=0
for d in /proc/irq/[0-9]*/; do
  f="$d/smp_affinity_list"
  [ -f "$f" ] || continue
  if echo "$TARGET" > "$f" 2>/dev/null; then
    steered=$((steered + 1))
  else
    rejected=$((rejected + 1))
  fi
done

# post-state: how many IRQ masks still allow the RT core (intent check)
onrt=0
for d in /proc/irq/[0-9]*/; do
  f="$d/smp_affinity_list"; [ -f "$f" ] || continue
  case " $(expand "$(tr ',-' '  ' < "$f")") " in *" $RT "*) onrt=$((onrt + 1)) ;; esac
done

printf '{"mode":"%s","rtcpu":"%s","park_cpu":"%s","steered_ok":%d,"rejected":%d,"irqs_allowed_on_rtcpu":%d}\n' \
  "$MODE" "$RT" "$PARK" "$steered" "$rejected" "$onrt"
