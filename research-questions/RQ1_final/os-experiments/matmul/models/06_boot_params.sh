#!/usr/bin/env bash
# 06_boot_params.sh <namespace> <status|apply|restore>
#
# SUBTRACTIVE: removes the mitigations=off + transparent_hugepage=never +
# rcu_nocb_poll bundle the full baseline already applied (harden-core.sh's
# own grub line, marked "# rq1-harden-bootparams"), leaving isolcpus/
# nohz_full/rcu_nocbs/systemd-contain/irq-steer as baseline.
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
BASELINE_MARK="# rq1-harden-bootparams (added by node-prep/harden-core.sh)"
MY_MARK="# rq1-os-sensitivity-bootparams-removed (added by 06_boot_params.sh)"

status() {
  echo "--- THP ---"; cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null
  echo "--- mitigations (cmdline) ---"
  grep -o "mitigations=[a-z]*" /proc/cmdline || echo "not set (default = on)"
  echo "--- rcu_nocb_poll (cmdline) ---"
  grep -q "rcu_nocb_poll" /proc/cmdline && echo "present" || echo "not set"
}

apply() {  # remove the bundle -- baseline's own line
  if grep -q "$MY_MARK" "$GRUB" 2>/dev/null; then
    echo "boot-params bundle already removed; nothing to do."; return 0
  fi
  if ! grep -q "$BASELINE_MARK" "$GRUB" 2>/dev/null; then
    echo "ERROR: full-isolation baseline mark not found in $GRUB -- apply the baseline first." >&2
    exit 1
  fi
  cp -n "$GRUB" "$GRUB.rq1-bootparams-removed.orig"
  python3 - "$GRUB" <<'PY'
import re, sys
path = sys.argv[1]
lines = open(path).read().splitlines()
out = []
for line in lines:
    if line.startswith("GRUB_CMDLINE_LINUX="):
        line = re.sub(r'\s*mitigations=off', '', line)
        line = re.sub(r'\s*transparent_hugepage=never', '', line)
        line = re.sub(r'\s*rcu_nocb_poll', '', line)
    out.append(line)
open(path, "w").write("\n".join(out) + "\n")
PY
  echo "$MY_MARK" >> "$GRUB"
  echo "removed mitigations=off/transparent_hugepage=never/rcu_nocb_poll from $GRUB."
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo always > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
  echo ">>> REBOOT REQUIRED for mitigations=on to take effect. THP reset to always immediately. <<<"
}

restore() {  # put the bundle back -- exactly as harden-core.sh's boot_params() does
  [ -f "$GRUB.rq1-bootparams-removed.orig" ] || { echo "no backup found; nothing to restore" >&2; exit 1; }
  cp "$GRUB.rq1-bootparams-removed.orig" "$GRUB"
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo never > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
  echo "restored boot-params bundle -- back to full baseline. REBOOT REQUIRED for mitigations=off."
}

case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: <status|apply|restore>"; exit 2 ;;
esac
CORE
