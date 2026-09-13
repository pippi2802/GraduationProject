#!/usr/bin/env bash
# verify_scenario.sh <namespace> <scenario> [keep_cpu]
#
# PASS/FAIL check of live kernel/systemd state against what a scenario
# SHOULD have produced, not a raw status dump -- run this AFTER rebooting
# (for the grub-based scenarios), it reads the actually-booted state via
# /sys and /proc, not the staged grub file.
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

isolcpus_active() { [ -s /sys/devices/system/cpu/isolated ]; }
nohz_active()     { [ -s /sys/devices/system/cpu/nohz_full ]; }
rcu_nocbs_active(){ grep -q "rcu_nocbs=" /proc/cmdline; }
mitigations_off() { grep -q "mitigations=off" /proc/cmdline; }
rcu_poll_active() { grep -q "rcu_nocb_poll" /proc/cmdline; }
thp_never()       { grep -q "\[never\]" /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null; }
thp_always()      { grep -q "\[always\]" /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null; }
smt_on()          { [ "$(cat /sys/devices/system/cpu/smt/control 2>/dev/null)" = "on" ]; }
systemd_contain_active() {
  local v; v=$(systemctl show system.slice -p AllowedCPUs 2>/dev/null | cut -d= -f2)
  [ -n "$v" ] && [ "$v" != "" ]
}
irq_steer_active() { systemctl is-active --quiet rq1-os-sensitivity-irq-steer.service 2>/dev/null; }

case "$SCEN" in
  isolcpus_only)
    isolcpus_active && check "isolcpus active" 1 || check "isolcpus active" 0
    nohz_active && check "nohz_full should be INACTIVE (isolcpus-only scenario)" 0 || check "nohz_full inactive, as expected" 1
    rcu_nocbs_active && check "rcu_nocbs should be INACTIVE (isolcpus-only scenario)" 0 || check "rcu_nocbs inactive, as expected" 1
    ;;
  nohz_full_only)
    nohz_active && check "nohz_full active" 1 || check "nohz_full active" 0
    isolcpus_active && check "isolcpus should be INACTIVE (nohz-only scenario)" 0 || check "isolcpus inactive, as expected" 1
    ;;
  rcu_nocbs_only)
    rcu_nocbs_active && check "rcu_nocbs active" 1 || check "rcu_nocbs active" 0
    isolcpus_active && check "isolcpus should be INACTIVE (rcu-only scenario)" 0 || check "isolcpus inactive, as expected" 1
    ;;
  systemd_contain)
    systemd_contain_active && check "system.slice/user.slice AllowedCPUs set" 1 || check "system.slice/user.slice AllowedCPUs set" 0
    ;;
  irq_steer)
    irq_steer_active && check "rq1-os-sensitivity-irq-steer.service active" 1 || check "rq1-os-sensitivity-irq-steer.service active" 0
    bad=0
    for f in /proc/irq/*/smp_affinity_list; do
      v=$(cat "$f" 2>/dev/null); [ "$v" = "$KEEP" ] || bad=$((bad+1))
    done
    check "no steerable IRQs left off cpu$KEEP ($bad still elsewhere)" "$([ "$bad" -eq 0 ] && echo 1 || echo 0)"
    ;;
  boot_params)
    mitigations_off && check "mitigations=off" 1 || check "mitigations=off" 0
    thp_never && check "transparent_hugepage=never" 1 || check "transparent_hugepage=never" 0
    rcu_poll_active && check "rcu_nocb_poll present" 1 || check "rcu_nocb_poll present" 0
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
