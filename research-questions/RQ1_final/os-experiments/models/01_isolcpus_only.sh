#!/usr/bin/env bash
# 01_isolcpus_only.sh <namespace> <status|apply|restore>
#
# SUBTRACTIVE design: starting from the FULL isolation baseline (already
# applied by kubedeadline-experiments/node-prep/isolate-core.sh -- one grub
# line carrying isolcpus=/nohz_full=/rcu_nocbs= together, marked
# "# rq1-isolation (added by node-prep/isolate-core.sh)"), this scenario
# REMOVES just the isolcpus= token from that line, leaving nohz_full=/
# rcu_nocbs= (and everything else in the baseline) untouched.
#
# apply()  = isolcpus removed, rest of baseline intact  (the scenario)
# restore() = isolcpus put back                          (back to full baseline)
#
# Requires the full-isolation baseline to already be applied on this node --
# refuses to run if isolate-core.sh's own mark isn't found in grub.
set -euo pipefail
NS="${1:?usage: 01_isolcpus_only.sh <namespace> <status|apply|restore>}"
MODE="${2:?usage: 01_isolcpus_only.sh <namespace> <status|apply|restore>}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[01_isolcpus_only] ns=$NS agent=$AGENT mode=$MODE"

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" <<'CORE'
set -u
MODE="$1"
GRUB=/etc/default/grub
BASELINE_MARK="# rq1-isolation (added by node-prep/isolate-core.sh)"
MY_MARK="# rq1-os-sensitivity-isolcpus-removed (added by 01_isolcpus_only.sh)"

status() {
  echo "--- isolated cpus (kernel-reported) ---"
  cat /sys/devices/system/cpu/isolated 2>/dev/null || echo "(none -- isolcpus not active)"
  echo "--- nohz_full cpus (should still be active) ---"
  cat /sys/devices/system/cpu/nohz_full 2>/dev/null || echo "(not reported)"
}

apply() {
  if grep -q "$MY_MARK" "$GRUB" 2>/dev/null; then
    echo "isolcpus already removed; nothing to do."; return 0
  fi
  if ! grep -q "$BASELINE_MARK" "$GRUB" 2>/dev/null; then
    echo "ERROR: full-isolation baseline mark not found in $GRUB -- apply the baseline first." >&2
    exit 1
  fi
  cp -n "$GRUB" "$GRUB.rq1-isolcpus-removed.orig"
  python3 - "$GRUB" <<'PY'
import re, sys
path = sys.argv[1]
lines = open(path).read().splitlines()
out = []
for line in lines:
    if line.startswith("GRUB_CMDLINE_LINUX=") and "isolcpus=" in line:
        line = re.sub(r'\s*isolcpus=\S+', '', line)
    out.append(line)
open(path, "w").write("\n".join(out) + "\n")
PY
  echo "$MY_MARK" >> "$GRUB"
  echo "removed isolcpus= from $GRUB (nohz_full=/rcu_nocbs= left as baseline has them)."
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo ">>> REBOOT REQUIRED to take effect. <<<"
}

restore() {
  [ -f "$GRUB.rq1-isolcpus-removed.orig" ] || { echo "no backup found; nothing to restore" >&2; exit 1; }
  cp "$GRUB.rq1-isolcpus-removed.orig" "$GRUB"
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo "restored isolcpus= -- back to full baseline. REBOOT REQUIRED."
}

case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: <status|apply|restore>"; exit 2 ;;
esac
CORE
