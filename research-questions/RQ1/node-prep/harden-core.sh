#!/usr/bin/env bash
# harden-core.sh <status|systemd-contain|irq-steer|boot-params|smt-off|restore-all>
#
# Runs ON THE HOST via nsenter from the privileged rq1-agent (same technique
# as isolate-core.sh -- hostPID + privileged already give `nsenter --target 1`
# everything it needs, including systemd/dbus and /proc/irq, no extra mounts).
#
# Actions beyond isolate.sh's isolcpus/nohz_full/rcu_nocbs:
#   systemd-contain  hard-clamps system.slice/user.slice to keep_cpu only, via
#                    cgroup v2 AllowedCPUs= (NOT kubepods.slice -- that's where
#                    target/competitor pods live, touching it breaks them).
#                    No reboot; persists via a systemd drop-in.
#   irq-steer        moves every steerable device IRQ onto keep_cpu, installs a
#                    oneshot systemd unit so it's re-applied on every future
#                    boot (the kernel resets /proc/irq/* affinity every boot
#                    regardless of anything else). No reboot needed now.
#   boot-params      appends mitigations=off + transparent_hugepage=never to
#                    the SAME grub line isolate-core.sh uses. REBOOT REQUIRED.
#                    Marked separately so `restore-all` can remove just this
#                    block without touching isolate-core.sh's own isolcpus line.
#   smt-off          echo off > smt/control. No reboot, but changes logical
#                    cpu count/numbering -- re-run isolate-core.sh status after.
#   status           dumps current state of all of the above in one pass.
#   restore-all      undoes systemd-contain + irq-steer + boot-params + smt-off
#                    (boot-params restore still needs a reboot to take effect).
set -u
MODE="${1:?usage: harden-core.sh <status|systemd-contain|irq-steer|boot-params|smt-off|restore-all> [keep_cpu]}"
KEEP="${2:-0}"
GRUB=/etc/default/grub
MARK="# rq1-harden-bootparams (added by node-prep/harden-core.sh)"
IRQ_UNIT=/etc/systemd/system/rq1-irq-steer.service
DROPIN_DIR_SYS=/etc/systemd/system/system.slice.d
DROPIN_DIR_USR=/etc/systemd/system/user.slice.d

systemd_contain() {
  mkdir -p "$DROPIN_DIR_SYS" "$DROPIN_DIR_USR"
  printf '[Slice]\nAllowedCPUs=%s\n' "$KEEP" > "$DROPIN_DIR_SYS/rq1-harden.conf"
  printf '[Slice]\nAllowedCPUs=%s\n' "$KEEP" > "$DROPIN_DIR_USR/rq1-harden.conf"
  systemctl daemon-reload
  systemctl set-property system.slice AllowedCPUs="$KEEP"
  systemctl set-property user.slice AllowedCPUs="$KEEP"
  echo "[harden] system.slice + user.slice clamped to cpu$KEEP (kubepods.slice left untouched)."
  echo "[harden] verify: systemctl show system.slice -p AllowedCPUs"
}

irq_steer() {
  for f in /proc/irq/*/smp_affinity_list; do
    echo "$KEEP" > "$f" 2>/dev/null || true
  done
  cat > "$IRQ_UNIT" <<EOF
[Unit]
Description=RQ1 -- steer all device IRQs onto cpu$KEEP at boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'for f in /proc/irq/*/smp_affinity_list; do echo $KEEP > "\$f" 2>/dev/null || true; done'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now rq1-irq-steer.service
  echo "[harden] IRQs steered onto cpu$KEEP now, and rq1-irq-steer.service will redo this on every future boot."
  echo "[harden] verify: for f in /proc/irq/*/smp_affinity_list; do v=\$(cat \$f); case \"\$v\" in *1*|*2*|*3*) echo \"\$f: \$v\";; esac; done"
}

boot_params() {
  if grep -q "$MARK" "$GRUB" 2>/dev/null; then
    echo "[harden] already applied (marker found in $GRUB); nothing to do."
    return 0
  fi
  if [ ! -f "$GRUB" ]; then
    echo "[harden] ERROR: $GRUB not found -- aborting, no changes made." >&2
    return 1
  fi
  {
    echo "$MARK"
    echo "GRUB_CMDLINE_LINUX=\"\$GRUB_CMDLINE_LINUX mitigations=off transparent_hugepage=never\""
  } >> "$GRUB"
  echo "[harden] appended mitigations=off transparent_hugepage=never to $GRUB"
  if command -v update-grub >/dev/null 2>&1; then
    update-grub
  elif command -v grub2-mkconfig >/dev/null 2>&1; then
    grub2-mkconfig -o /boot/grub2/grub.cfg
  else
    echo "[harden] ERROR: neither update-grub nor grub2-mkconfig found; staged but NOT regenerated." >&2
    return 1
  fi
  # also flip THP right now so you don't need the reboot just to see this half take effect
  echo never > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true
  echo "[harden] grub config regenerated. >>> REBOOT REQUIRED for mitigations=off to take effect. <<<"
  echo "[harden] (transparent_hugepage=never was also applied immediately, no reboot needed for that half)"
}

smt_off() {
  echo "[harden] cpu count before: $(nproc)"
  echo off > /sys/devices/system/cpu/smt/control 2>/dev/null || {
    echo "[harden] ERROR: could not write smt/control (unsupported, or something's still running on a sibling?)" >&2
    return 1
  }
  echo "[harden] SMT control: $(cat /sys/devices/system/cpu/smt/control)"
  echo "[harden] cpu count after: $(nproc)"
  echo "[harden] >>> core numbering may have shifted -- re-run isolate-core.sh status to confirm isolcpus still maps correctly. <<<"
}

status() {
  echo "--- systemd containment ---"
  systemctl show system.slice -p AllowedCPUs 2>/dev/null
  systemctl show user.slice -p AllowedCPUs 2>/dev/null
  echo "--- IRQ steering unit ---"
  systemctl is-enabled rq1-irq-steer.service 2>/dev/null || echo "rq1-irq-steer.service: not installed"
  echo "--- IRQs still allowed on cpu1-3 ---"
  for f in /proc/irq/*/smp_affinity_list; do v=$(cat "$f" 2>/dev/null); case "$v" in *1*|*2*|*3*) echo "$f: $v";; esac; done
  echo "--- THP ---"
  cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null
  echo "--- mitigations (cmdline) ---"
  grep -o "mitigations=[a-z]*" /proc/cmdline || echo "not set (default = on)"
  echo "--- SMT ---"
  cat /sys/devices/system/cpu/smt/control 2>/dev/null
  echo "--- cpu count ---"
  nproc
}

restore_all() {
  rm -f "$DROPIN_DIR_SYS/rq1-harden.conf" "$DROPIN_DIR_USR/rq1-harden.conf"
  systemctl daemon-reload
  systemctl set-property system.slice AllowedCPUs="" 2>/dev/null || true
  systemctl set-property user.slice AllowedCPUs="" 2>/dev/null || true
  echo "[harden] systemd containment removed."

  systemctl disable --now rq1-irq-steer.service 2>/dev/null || true
  rm -f "$IRQ_UNIT"
  systemctl daemon-reload
  echo "[harden] IRQ steering unit removed (existing affinity left as-is, not reset)."

  if grep -q "$MARK" "$GRUB" 2>/dev/null; then
    grep -v -A1 "$MARK" "$GRUB" | grep -v "^--$" > "$GRUB.tmp" && mv "$GRUB.tmp" "$GRUB"
    if command -v update-grub >/dev/null 2>&1; then update-grub
    elif command -v grub2-mkconfig >/dev/null 2>&1; then grub2-mkconfig -o /boot/grub2/grub.cfg
    fi
    echo "[harden] boot-params block removed from $GRUB. REBOOT REQUIRED to take effect."
  fi

  echo on > /sys/devices/system/cpu/smt/control 2>/dev/null || true
  echo "[harden] SMT control restored to: $(cat /sys/devices/system/cpu/smt/control 2>/dev/null)"
}

case "$MODE" in
  status) status ;;
  systemd-contain) systemd_contain ;;
  irq-steer) irq_steer ;;
  boot-params) boot_params ;;
  smt-off) smt_off ;;
  restore-all) restore_all ;;
  *) echo "usage: harden-core.sh <status|systemd-contain|irq-steer|boot-params|smt-off|restore-all> [keep_cpu]"; exit 2 ;;
esac
