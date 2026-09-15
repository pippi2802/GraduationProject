#!/usr/bin/env bash
# verify_scenario.sh <namespace> <scenario> [keep_cpu]
#
# PASS/FAIL check of live kernel/systemd state against a SUBTRACTIVE
# scenario: full isolation baseline, with exactly ONE lever removed.
# Run AFTER rebooting (for the grub-based scenarios) -- reads actually-booted
# state via /sys and /proc, not the staged grub file.
#
# scenario: isolcpus_only | nohz_full_only | rcu_nocbs_only |
#           systemd_contain | irq_steer | boot_params | worst_case
set -euo pipefail
NS="${1:?usage: verify_scenario.sh <namespace> <scenario> [keep_cpu]}"
SCEN="${2:?usage: verify_scenario.sh <namespace> <scenario> [keep_cpu]}"
KEEP="${3:-0}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[verify_scenario] ns=$NS agent=$AGENT scenario=$SCEN keep_cpu=$KEEP"
echo

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$SCEN" "$KEEP" <<'CORE'
set -u
SCEN="$1"; KEEP="$2"
PASS=0; FAIL=0
check() {
  local desc="$1" ok="$2"
  if [ "$ok" = 1 ]; then echo "  PASS: $desc"; PASS=$((PASS+1))
  else echo "  FAIL: $desc"; FAIL=$((FAIL+1)); fi
}

isolcpus_active() { [ -n "$(cat /sys/devices/system/cpu/isolated 2>/dev/null)" ]; }
nohz_active()     { [ -n "$(cat /sys/devices/system/cpu/nohz_full 2>/dev/null)" ]; }
rcu_nocbs_active(){ grep -q "rcu_nocbs=" /proc/cmdline; }
mitigations_off() { grep -q "mitigations=off" /proc/cmdline; }
rcu_poll_active() { grep -q "rcu_nocb_poll" /proc/cmdline; }
thp_never()       { grep -q "\[never\]" /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null; }
# "default" here means NOT the harden-core bundle's forced [never] -- this
# platform's real distro default is [madvise], not [always], confirmed
# empirically on 07-model1's node post-reboot (2026-09-15).
thp_always()      { ! grep -q "\[never\]" /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null; }
smt_on()          { [ "$(cat /sys/devices/system/cpu/smt/control 2>/dev/null)" = "on" ]; }
systemd_contain_active() {
  local v; v=$(systemctl show system.slice -p AllowedCPUs 2>/dev/null | cut -d= -f2)
  [ -n "$v" ] && [ "$v" != "" ]
}
irq_steer_active() { systemctl is-active --quiet rq1-irq-steer.service 2>/dev/null; }

# helper: assert baseline pieces NOT under test are still intact
baseline_isolcpus() { isolcpus_active && check "isolcpus still active (part of baseline)" 1 || check "isolcpus still active (part of baseline)" 0; }
baseline_nohz()     { nohz_active && check "nohz_full still active (part of baseline)" 1 || check "nohz_full still active (part of baseline)" 0; }
baseline_rcu()      { rcu_nocbs_active && check "rcu_nocbs still active (part of baseline)" 1 || check "rcu_nocbs still active (part of baseline)" 0; }
baseline_systemd()  { systemd_contain_active && check "systemd containment still active (part of baseline)" 1 || check "systemd containment still active (part of baseline)" 0; }
baseline_irq()      { irq_steer_active && check "IRQ steering still active (part of baseline)" 1 || check "IRQ steering still active (part of baseline)" 0; }
baseline_boot()     { mitigations_off && thp_never && check "boot-params bundle still active (part of baseline)" 1 || check "boot-params bundle still active (part of baseline)" 0; }

case "$SCEN" in
  isolcpus_only)
    isolcpus_active && check "isolcpus should be REMOVED" 0 || check "isolcpus removed, as expected" 1
    baseline_nohz; baseline_rcu
    ;;
  nohz_full_only)
    nohz_active && check "nohz_full should be REMOVED" 0 || check "nohz_full removed, as expected" 1
    baseline_isolcpus; baseline_rcu
    ;;
  rcu_nocbs_only)
    rcu_nocbs_active && check "rcu_nocbs should be REMOVED" 0 || check "rcu_nocbs removed, as expected" 1
    baseline_isolcpus; baseline_nohz
    ;;
  systemd_contain)
    systemd_contain_active && check "systemd containment should be REMOVED" 0 || check "systemd containment removed, as expected" 1
    baseline_isolcpus; baseline_nohz; baseline_rcu; baseline_irq; baseline_boot
    ;;
  irq_steer)
    irq_steer_active && check "IRQ steering should be REMOVED" 0 || check "IRQ steering removed, as expected" 1
    baseline_isolcpus; baseline_nohz; baseline_rcu; baseline_systemd; baseline_boot
    ;;
  boot_params)
    mitigations_off && check "mitigations should be back ON (removed)" 0 || check "mitigations back on, as expected" 1
    thp_never && check "THP should be back to always (removed)" 0 || check "THP back to always, as expected" 1
    rcu_poll_active && check "rcu_nocb_poll should be REMOVED" 0 || check "rcu_nocb_poll removed, as expected" 1
    baseline_isolcpus; baseline_nohz; baseline_rcu; baseline_systemd; baseline_irq
    ;;
  worst_case)
    isolcpus_active && check "isolcpus should be INACTIVE" 0 || check "isolcpus inactive" 1
    nohz_active && check "nohz_full should be INACTIVE" 0 || check "nohz_full inactive" 1
    rcu_nocbs_active && check "rcu_nocbs should be INACTIVE" 0 || check "rcu_nocbs inactive" 1
    mitigations_off && check "mitigations should be ON (default)" 0 || check "mitigations default (on)" 1
    thp_always && check "THP should be always (default)" 1 || check "THP should be always (default)" 0
    smt_on && check "SMT should be on (default)" 1 || check "SMT should be on (default)" 0
    systemd_contain_active && check "systemd containment should be REMOVED" 0 || check "systemd containment removed" 1
    irq_steer_active && check "IRQ steering should be REMOVED" 0 || check "IRQ steering removed" 1
    ;;
  *)
    echo "unknown scenario: $SCEN" >&2; exit 2 ;;
esac

echo
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
CORE
