#!/usr/bin/env bash
# 07_worst_case.sh <namespace> <status|apply>
#
# OS-sensitivity floor scenario: strip EVERY known RQ1 isolation/hardening
# mark (both this directory's 01-06 scripts AND kubedeadline-experiments'
# original node-prep isolate/harden marks, in case this node was previously
# set up as a KubeDeadline-domain baseline node) -- true "nothing configured"
# state, the other bookend from the fully-isolated baseline.
#
# Deliberately doesn't try to track which specific script's backup file to
# restore (each of 01/02/03/06 writes a differently-named .orig, and the
# original node-prep scripts write yet another) -- instead strips any GRUB
# line containing the known tokens directly, which is robust regardless of
# which combination of scripts previously ran on this node.
set -euo pipefail
NS="${1:?usage: 07_worst_case.sh <namespace> <status|apply>}"
MODE="${2:?usage: 07_worst_case.sh <namespace> <status|apply>}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[07_worst_case] ns=$NS agent=$AGENT mode=$MODE"

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" <<'CORE'
set -u
MODE="$1"
GRUB=/etc/default/grub

status() {
  echo "--- /proc/cmdline ---"; cat /proc/cmdline
  echo "--- isolated cpus ---"; cat /sys/devices/system/cpu/isolated 2>/dev/null || echo "(none)"
  echo "--- systemd containment ---"
  systemctl show system.slice -p AllowedCPUs 2>/dev/null
  echo "--- IRQ steering units ---"
  systemctl is-enabled rq1-irq-steer.service 2>/dev/null || echo "rq1-irq-steer.service: not installed"
  systemctl is-enabled rq1-os-sensitivity-irq-steer.service 2>/dev/null || echo "rq1-os-sensitivity-irq-steer.service: not installed"
  echo "--- THP ---"; cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null
  echo "--- SMT ---"; cat /sys/devices/system/cpu/smt/control 2>/dev/null
}

apply() {
  # 1. strip any grub line carrying an isolation/hardening token, regardless
  #    of which script (old node-prep or new 01/02/03/06) added it.
  if [ -f "$GRUB" ]; then
    cp -n "$GRUB" "$GRUB.rq1-worst-case-pre.orig"
    grep -vE "isolcpus=|nohz_full=|rcu_nocbs=|mitigations=off|transparent_hugepage=never|rcu_nocb_poll|# rq1-" "$GRUB" > "$GRUB.tmp" && mv "$GRUB.tmp" "$GRUB"
    command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
    echo "stripped all RQ1 isolation/hardening tokens from $GRUB. REBOOT REQUIRED."
  fi

  # 2. remove systemd containment drop-ins (both naming generations)
  rm -f /etc/systemd/system/system.slice.d/rq1-harden.conf \
        /etc/systemd/system/user.slice.d/rq1-harden.conf \
        /etc/systemd/system/system.slice.d/rq1-os-sensitivity.conf \
        /etc/systemd/system/user.slice.d/rq1-os-sensitivity.conf
  systemctl daemon-reload
  systemctl set-property system.slice AllowedCPUs="" 2>/dev/null || true
  systemctl set-property user.slice AllowedCPUs="" 2>/dev/null || true
  echo "systemd containment removed."

  # 3. remove IRQ steering units (both naming generations)
  systemctl disable --now rq1-irq-steer.service 2>/dev/null || true
  systemctl disable --now rq1-os-sensitivity-irq-steer.service 2>/dev/null || true
  rm -f /etc/systemd/system/rq1-irq-steer.service /etc/systemd/system/rq1-os-sensitivity-irq-steer.service
  systemctl daemon-reload
  echo "IRQ steering units removed (existing affinity left as-is, not reset)."

  # 4. reset THP and SMT to distro defaults
  echo always > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
  echo on > /sys/devices/system/cpu/smt/control 2>/dev/null || true
  echo "THP reset to always, SMT reset to on."
  echo ">>> REBOOT REQUIRED for the grub-level changes to take effect. <<<"
}

case "$MODE" in
  status) status ;;
  apply) apply ;;
  *) echo "usage: <status|apply>"; exit 2 ;;
esac
CORE
