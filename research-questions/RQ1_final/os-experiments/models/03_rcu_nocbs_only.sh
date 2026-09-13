#!/usr/bin/env bash
# 03_rcu_nocbs_only.sh <namespace> <status|apply|restore> [keep_cpu]
#
# OS-sensitivity scenario: rcu_nocbs= ONLY (no isolcpus, no nohz_full).
# Same coupling caveat as nohz_full: rcu_nocbs offloads RCU callback
# processing off these cpus, most valuable when nothing else can interrupt
# them -- without isolcpus, other tasks can still land here, so a weak
# effect here means "rcu_nocbs alone doesn't help," not "doesn't matter."
set -euo pipefail
NS="${1:?usage: 03_rcu_nocbs_only.sh <namespace> <status|apply|restore> [keep_cpu]}"
MODE="${2:?usage: 03_rcu_nocbs_only.sh <namespace> <status|apply|restore> [keep_cpu]}"
KEEP="${3:-0}"

AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[03_rcu_nocbs_only] ns=$NS agent=$AGENT mode=$MODE keep_cpu=$KEEP"

kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- \
  bash -s -- "$MODE" "$KEEP" <<'CORE'
set -u
MODE="$1"; KEEP="$2"
GRUB=/etc/default/grub
MARK="# rq1-os-sensitivity-rcu-nocbs-only (added by 03_rcu_nocbs_only.sh)"
nproc_host=$(nproc); LAST=$((nproc_host - 1))
ISO=$(seq 0 "$LAST" | grep -vx "$KEEP" | paste -sd, -)

status() {
  echo "--- /proc/cmdline ---"; cat /proc/cmdline
  echo "--- rcu_nocbs (cmdline grep) ---"
  grep -o "rcu_nocbs=[0-9,-]*" /proc/cmdline || echo "(not set)"
}
apply() {
  if grep -q "$MARK" "$GRUB" 2>/dev/null; then
    echo "already applied; run 'restore' first to change keep_cpu."; return 0
  fi
  [ -f "$GRUB" ] || { echo "ERROR: $GRUB not found" >&2; exit 1; }
  cp -n "$GRUB" "$GRUB.rq1-rcu-nocbs-only.orig"
  { echo "$MARK"; echo "GRUB_CMDLINE_LINUX=\"\$GRUB_CMDLINE_LINUX rcu_nocbs=$ISO\""; } >> "$GRUB"
  echo "appended rcu_nocbs=$ISO (keeping cpu$KEEP) to $GRUB"
  command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg
  echo ">>> REBOOT REQUIRED to take effect. <<<"
}
restore() {
  [ -f "$GRUB.rq1-rcu-nocbs-only.orig" ] || { echo "no backup found; nothing to restore" >&2; exit 1; }
  cp "$GRUB.rq1-rcu-nocbs-only.orig" "$GRUB"
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
  echo "[03_rcu_nocbs_only] >>> boot config staged -- nothing takes effect until you reboot this node. <<<"
  echo "[03_rcu_nocbs_only] reboot the underlying VM, then: bash 03_rcu_nocbs_only.sh $NS status"
fi
