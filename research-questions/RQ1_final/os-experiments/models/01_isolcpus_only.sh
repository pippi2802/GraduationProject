#!/usr/bin/env bash
# 01_isolcpus_only.sh <namespace> <status|apply|restore> [keep_cpu]
#
# OS-sensitivity scenario: isolcpus= ONLY (no nohz_full, no rcu_nocbs), for
# whichever node currently hosts the workload under <namespace> (via the
# rq1-agent DaemonSet + nsenter into the host -- same technique as
# kubedeadline-experiments/node-prep/isolate.sh, standalone here on purpose).
#
# Boot-config change -- takes effect only after a reboot, which this script
# deliberately does not trigger. Reboot yourself, then verify with 'status'.
set -euo pipefail
NS="${1:?usage: 01_isolcpus_only.sh <namespace> <status|apply|restore> [keep_cpu]}"
MODE="${2:?usage: 01_isolcpus_only.sh <namespace> <status|apply|restore> [keep_cpu]}"
KEEP="${3:-0}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[01_isolcpus_only] ns=$NS agent=$AGENT mode=$MODE keep_cpu=$KEEP"

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" "$KEEP" <<'CORE'
set -u
MODE="$1"; KEEP="$2"
GRUB=/etc/default/grub
MARK="# rq1-os-sensitivity-isolcpus-only (added by 01_isolcpus_only.sh)"
nproc_host=$(nproc); LAST=$((nproc_host - 1))
ISO=$(seq 0 "$LAST" | grep -vx "$KEEP" | paste -sd, -)

status() {
  echo "--- /proc/cmdline ---"; cat /proc/cmdline
  echo "--- isolated cpus (kernel-reported) ---"
  cat /sys/devices/system/cpu/isolated 2>/dev/null || echo "(none -- isolcpus not active)"
}
apply() {
  if grep -q "$MARK" "$GRUB" 2>/dev/null; then
    echo "already applied; run 'restore' first to change keep_cpu."; return 0
  fi
  [ -f "$GRUB" ] || { echo "ERROR: $GRUB not found" >&2; exit 1; }
  cp -n "$GRUB" "$GRUB.rq1-isolcpus-only.orig"
  { echo "$MARK"; echo "GRUB_CMDLINE_LINUX=\"\$GRUB_CMDLINE_LINUX isolcpus=$ISO\""; } >> "$GRUB"
  echo "appended isolcpus=$ISO (keeping cpu$KEEP) to $GRUB"
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo ">>> REBOOT REQUIRED to take effect. <<<"
}
restore() {
  [ -f "$GRUB.rq1-isolcpus-only.orig" ] || { echo "no backup found; nothing to restore" >&2; exit 1; }
  cp "$GRUB.rq1-isolcpus-only.orig" "$GRUB"
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
  echo "[01_isolcpus_only] >>> boot config staged -- nothing takes effect until you reboot this node. <<<"
  echo "[01_isolcpus_only] reboot the underlying VM, then: bash 01_isolcpus_only.sh $NS status"
fi
