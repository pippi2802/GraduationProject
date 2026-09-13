#!/usr/bin/env bash
# 02_nohz_full_only.sh <namespace> <status|apply|restore> [keep_cpu]
#
# OS-sensitivity scenario: nohz_full= ONLY (no isolcpus, no rcu_nocbs).
# NOTE: nohz_full's own benefit (stop the periodic scheduler tick when only
# one task is runnable on that cpu) is designed to work WITH isolcpus -- here
# isolcpus is deliberately absent, so the general scheduler can still place
# other tasks on these cpus, meaning "only one task runnable" may rarely
# hold. A weak effect here can mean "nohz_full alone doesn't help," not
# necessarily "nohz_full doesn't matter" -- state that caveat in the writeup.
set -euo pipefail
NS="${1:?usage: 02_nohz_full_only.sh <namespace> <status|apply|restore> [keep_cpu]}"
MODE="${2:?usage: 02_nohz_full_only.sh <namespace> <status|apply|restore> [keep_cpu]}"
KEEP="${3:-0}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[02_nohz_full_only] ns=$NS agent=$AGENT mode=$MODE keep_cpu=$KEEP"

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" "$KEEP" <<'CORE'
set -u
MODE="$1"; KEEP="$2"
GRUB=/etc/default/grub
MARK="# rq1-os-sensitivity-nohz-full-only (added by 02_nohz_full_only.sh)"
nproc_host=$(nproc); LAST=$((nproc_host - 1))
ISO=$(seq 0 "$LAST" | grep -vx "$KEEP" | paste -sd, -)

status() {
  echo "--- /proc/cmdline ---"; cat /proc/cmdline
  echo "--- nohz_full cpus ---"
  cat /sys/devices/system/cpu/nohz_full 2>/dev/null || echo "(not reported)"
}
apply() {
  if grep -q "$MARK" "$GRUB" 2>/dev/null; then
    echo "already applied; run 'restore' first to change keep_cpu."; return 0
  fi
  [ -f "$GRUB" ] || { echo "ERROR: $GRUB not found" >&2; exit 1; }
  cp -n "$GRUB" "$GRUB.rq1-nohz-full-only.orig"
  { echo "$MARK"; echo "GRUB_CMDLINE_LINUX=\"\$GRUB_CMDLINE_LINUX nohz_full=$ISO\""; } >> "$GRUB"
  echo "appended nohz_full=$ISO (keeping cpu$KEEP) to $GRUB"
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo ">>> REBOOT REQUIRED to take effect. <<<"
}
restore() {
  [ -f "$GRUB.rq1-nohz-full-only.orig" ] || { echo "no backup found; nothing to restore" >&2; exit 1; }
  cp "$GRUB.rq1-nohz-full-only.orig" "$GRUB"
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo "restored $GRUB. REBOOT REQUIRED to take effect."
}
case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: <status|apply|restore>"; exit 2 ;;
esac
CORE

if [ "$MODE" = "apply" ] || [ "$MODE" = "restore" ]; then
  echo
  echo "[02_nohz_full_only] >>> boot config staged -- nothing takes effect until you reboot this node. <<<"
  echo "[02_nohz_full_only] reboot the underlying VM, then: bash 02_nohz_full_only.sh $NS status"
fi
