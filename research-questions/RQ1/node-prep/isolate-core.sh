#!/usr/bin/env bash
# isolate-core.sh <status|apply|restore> [keep_cpu]
#
# Runs ON THE HOST via nsenter from the privileged rq1-agent (hostPID + privileged
# already give it what `nsenter --target 1` needs -- no extra mounts required).
# Edits /etc/default/grub to add isolcpus=/nohz_full=/rcu_nocbs= for every logical
# cpu EXCEPT `keep_cpu` (default 0, left for kubelet/sshd/housekeeping), then
# regenerates the grub config.
#
# NOTE: this only rewrites the boot config -- the kernel cmdline only takes effect
# after a reboot, which this script deliberately does NOT trigger (rebooting the
# node kills every pod on it, including in-flight experiment pods). Reboot it
# yourself once you're ready (Azure VM restart / `sudo reboot` over SSH), then
# verify with: isolate-core.sh status.
set -u
MODE="${1:?usage: isolate-core.sh <status|apply|restore> [keep_cpu]}"
KEEP="${2:-0}"
GRUB=/etc/default/grub
MARK="# rq1-isolation (added by node-prep/isolate-core.sh)"

nproc_host=$(nproc)
LAST=$((nproc_host - 1))
# isolate every cpu except KEEP, as a comma list (paste keeps it on one line)
ISO=$(seq 0 "$LAST" | grep -vx "$KEEP" | paste -sd, -)

status() {
  echo "--- /proc/cmdline ---"; cat /proc/cmdline
  echo "--- isolated cpus (kernel-reported) ---"
  cat /sys/devices/system/cpu/isolated 2>/dev/null || echo "(none reported -- isolcpus not active)"
  echo "--- nohz_full cpus ---"
  cat /sys/devices/system/cpu/nohz_full 2>/dev/null || echo "(not reported)"
}

apply() {
  if grep -q "$MARK" "$GRUB" 2>/dev/null; then
    echo "[isolate] already applied (marker found in $GRUB); nothing to do."
    echo "[isolate] to change keep_cpu, run 'restore' first, then 'apply' again with the new value."
    return 0
  fi
  if [ ! -f "$GRUB" ]; then
    echo "[isolate] ERROR: $GRUB not found -- not a grub2/Debian-family host? aborting, no changes made." >&2
    return 1
  fi
  cp -n "$GRUB" "$GRUB.rq1.orig"   # keep exactly one pristine backup, never overwritten
  {
    echo "$MARK"
    echo "GRUB_CMDLINE_LINUX=\"\$GRUB_CMDLINE_LINUX isolcpus=$ISO nohz_full=$ISO rcu_nocbs=$ISO\""
  } >> "$GRUB"
  echo "[isolate] appended isolcpus/nohz_full/rcu_nocbs for cpus {$ISO} (keeping cpu$KEEP for housekeeping) to $GRUB"
  if command -v update-grub >/dev/null 2>&1; then
    update-grub
  elif command -v grub2-mkconfig >/dev/null 2>&1; then
    grub2-mkconfig -o /boot/grub2/grub.cfg
  else
    echo "[isolate] ERROR: neither update-grub nor grub2-mkconfig found; config staged but NOT regenerated -- run the equivalent for this distro manually." >&2
    return 1
  fi
  echo "[isolate] grub config regenerated."
  echo "[isolate] >>> REBOOT REQUIRED to take effect -- this script will not do it for you. <<<"
  echo "[isolate] after reboot, verify with: isolate-core.sh status"
}

restore() {
  if [ ! -f "$GRUB.rq1.orig" ]; then
    echo "[isolate] no backup ($GRUB.rq1.orig) found; nothing to restore." >&2
    return 1
  fi
  cp "$GRUB.rq1.orig" "$GRUB"
  echo "[isolate] restored $GRUB from backup."
  if command -v update-grub >/dev/null 2>&1; then update-grub
  elif command -v grub2-mkconfig >/dev/null 2>&1; then grub2-mkconfig -o /boot/grub2/grub.cfg
  fi
  echo "[isolate] grub config regenerated. REBOOT REQUIRED to take effect."
}

case "$MODE" in
  status) status ;;
  apply) apply ;;
  restore) restore ;;
  *) echo "usage: isolate-core.sh <status|apply|restore> [keep_cpu]"; exit 2 ;;
esac
