#!/usr/bin/env bash
# 06_boot_params.sh <namespace> <status|apply|restore>
#
# OS-sensitivity scenario: mitigations=off + transparent_hugepage=never +
# rcu_nocb_poll, bundled (kept as one scenario deliberately -- unlike
# isolcpus/nohz_full/rcu_nocbs these three are commonly treated as one "boot
# hardening" unit, not individually decomposed). REBOOT REQUIRED for
# mitigations=off; transparent_hugepage=never also applied immediately.
set -euo pipefail
NS="${1:?usage: 06_boot_params.sh <namespace> <status|apply|restore>}"
MODE="${2:?usage: 06_boot_params.sh <namespace> <status|apply|restore>}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[06_boot_params] ns=$NS agent=$AGENT mode=$MODE"

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" <<'CORE'
set -u
MODE="$1"
GRUB=/etc/default/grub
MARK="# rq1-os-sensitivity-boot-params (added by 06_boot_params.sh)"

status() {
  echo "--- THP ---"; cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null
  echo "--- mitigations (cmdline) ---"
  grep -o "mitigations=[a-z]*" /proc/cmdline || echo "not set (default = on)"
  echo "--- rcu_nocb_poll (cmdline) ---"
  grep -q "rcu_nocb_poll" /proc/cmdline && echo "present" || echo "not set"
}
apply() {
  local tokens=" mitigations=off transparent_hugepage=never rcu_nocb_poll"
  if grep -q "$MARK" "$GRUB" 2>/dev/null; then
    echo "already applied; nothing to do."; return 0
  fi
  [ -f "$GRUB" ] || { echo "ERROR: $GRUB not found" >&2; exit 1; }
  cp -n "$GRUB" "$GRUB.rq1-boot-params.orig"
  { echo "$MARK"; echo "GRUB_CMDLINE_LINUX=\"\$GRUB_CMDLINE_LINUX$tokens\""; } >> "$GRUB"
  echo "appended:$tokens to $GRUB"
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo never > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
  echo ">>> REBOOT REQUIRED for mitigations=off/rcu_nocb_poll. transparent_hugepage=never already applied. <<<"
}
restore() {
  [ -f "$GRUB.rq1-boot-params.orig" ] || { echo "no backup found; nothing to restore" >&2; exit 1; }
  cp "$GRUB.rq1-boot-params.orig" "$GRUB"
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo always > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
  echo "restored $GRUB. REBOOT REQUIRED to take effect."
}
case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: <status|apply|restore>"; exit 2 ;;
esac
CORE
