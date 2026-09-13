#!/usr/bin/env bash
# 02_nohz_full_only.sh <namespace> <status|apply|restore>
#
# SUBTRACTIVE: removes just the nohz_full= token from the existing full
# isolation baseline (isolate-core.sh's grub line), leaving isolcpus=/
# rcu_nocbs= intact. Requires the baseline to already be applied.
set -euo pipefail
NS="${1:?usage: 02_nohz_full_only.sh <namespace> <status|apply|restore>}"
MODE="${2:?usage: 02_nohz_full_only.sh <namespace> <status|apply|restore>}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[02_nohz_full_only] ns=$NS agent=$AGENT mode=$MODE"

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" <<'CORE'
set -u
MODE="$1"
GRUB=/etc/default/grub
BASELINE_MARK="# rq1-isolation (added by node-prep/isolate-core.sh)"
MY_MARK="# rq1-os-sensitivity-nohz-full-removed (added by 02_nohz_full_only.sh)"

status() {
  echo "--- isolated cpus (should still be active) ---"
  cat /sys/devices/system/cpu/isolated 2>/dev/null || echo "(none)"
  echo "--- nohz_full cpus ---"
  cat /sys/devices/system/cpu/nohz_full 2>/dev/null || echo "(not reported -- nohz_full inactive)"
}

apply() {
  if grep -q "$MY_MARK" "$GRUB" 2>/dev/null; then
    echo "nohz_full already removed; nothing to do."; return 0
  fi
  if ! grep -q "$BASELINE_MARK" "$GRUB" 2>/dev/null; then
    echo "ERROR: full-isolation baseline mark not found in $GRUB -- apply the baseline first." >&2
    exit 1
  fi
  cp -n "$GRUB" "$GRUB.rq1-nohz-full-removed.orig"
  python3 - "$GRUB" <<'PY'
import re, sys
path = sys.argv[1]
lines = open(path).read().splitlines()
out = []
for line in lines:
    if line.startswith("GRUB_CMDLINE_LINUX=") and "nohz_full=" in line:
        line = re.sub(r'\s*nohz_full=\S+', '', line)
    out.append(line)
open(path, "w").write("\n".join(out) + "\n")
PY
  echo "$MY_MARK" >> "$GRUB"
  echo "removed nohz_full= from $GRUB (isolcpus=/rcu_nocbs= left as baseline has them)."
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo ">>> REBOOT REQUIRED to take effect. <<<"
}

restore() {
  [ -f "$GRUB.rq1-nohz-full-removed.orig" ] || { echo "no backup found; nothing to restore" >&2; exit 1; }
  cp "$GRUB.rq1-nohz-full-removed.orig" "$GRUB"
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo "restored nohz_full= -- back to full baseline. REBOOT REQUIRED."
}

case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: <status|apply|restore>"; exit 2 ;;
esac
CORE
