#!/usr/bin/env bash
# lever.sh <namespace> <lever> <status|apply|restore> [keep_cpu]
#
# ADDITIVE design (RQ1_fromdefault): starting from the all-defaults node (levers/defaults.sh apply + reboot), switch ON exactly ONE lever.
# Same settings, tokens and units as the full-isolation baseline of RQ1_final (kubedeadline-experiments/node-prep/{isolate,harden}-core.sh),
# one lever at a time. Each grub-based lever carries its own mark so restore removes only that lever.
#
#   lever        what apply does                                                    reboot
#   isolcpus     isolcpus=<all cpus but keep_cpu> on the kernel command line        yes
#   nohz_full    nohz_full=<all cpus but keep_cpu>                                  yes
#   rcu_nocbs    rcu_nocbs=<all cpus but keep_cpu>                                  yes
#   boot_params  mitigations=off transparent_hugepage=never rcu_nocb_poll           yes (THP never also live)
#   systemd      system.slice + user.slice AllowedCPUs=<keep_cpu>                   no
#   irq_steer    all /proc/irq/*/smp_affinity_list -> keep_cpu + boot-time unit      no
#   freq_pin     governor=performance, turbo off, min=max (live)                    no  (deploy the agent WITHOUT SKIP_FREQ_PIN)
#
# <namespace> only selects the rq1-agent pod used to reach the node (nsenter into the host).
set -euo pipefail
NS="${1:?usage: lever.sh <namespace> <isolcpus|nohz_full|rcu_nocbs|boot_params|systemd|irq_steer|freq_pin> <status|apply|restore> [keep_cpu]}"
LEVER="${2:?lever}"; MODE="${3:?status|apply|restore}"; KEEP="${4:-0}"
AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -z "$AGENT" ] && { echo "ERROR: no rq1-agent pod in namespace $NS" >&2; exit 1; }
echo "[lever] ns=$NS agent=$AGENT lever=$LEVER mode=$MODE keep_cpu=$KEEP"
kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount --uts --ipc --net -- bash -s -- "$LEVER" "$MODE" "$KEEP" <<'CORE'
set -u
LEVER="$1"; MODE="$2"; KEEP="$3"
GRUB=/etc/default/grub
ISO=$(seq 0 $(( $(nproc) - 1 )) | grep -vx "$KEEP" | paste -sd, -)
IRQ_UNIT=/etc/systemd/system/rq1-fromdefault-irq-steer.service
DROP_SYS=/etc/systemd/system/system.slice.d/rq1-fromdefault.conf
DROP_USR=/etc/systemd/system/user.slice.d/rq1-fromdefault.conf
mark() { echo "# rq1-fromdefault-$1 (added by levers/lever.sh)"; }

regen() { command -v update-grub >/dev/null 2>&1 && update-grub || grub2-mkconfig -o /boot/grub2/grub.cfg; }
grub_add() {   # grub_add <name> <tokens>
  local name="$1" tokens="$2" m; m=$(mark "$name")
  grep -q -- "$m" "$GRUB" 2>/dev/null && { echo "$name already staged in $GRUB"; return 0; }
  cp -n "$GRUB" "$GRUB.rq1-fromdefault.orig"
  { echo "$m"; echo "GRUB_CMDLINE_LINUX=\"\$GRUB_CMDLINE_LINUX $tokens\""; } >> "$GRUB"
  regen; echo "appended '$tokens' to $GRUB. >>> REBOOT REQUIRED <<<"
}
grub_del() {   # grub_del <name>
  local m; m=$(mark "$1")
  grep -q -- "$m" "$GRUB" 2>/dev/null || { echo "$1 not staged; nothing to do"; return 0; }
  # drop the mark line and the single line after it
  awk -v m="$m" 'skip>0{skip--; next} $0==m{skip=1; next} {print}' "$GRUB" > "$GRUB.tmp" && mv "$GRUB.tmp" "$GRUB"
  regen; echo "removed $1 from $GRUB. >>> REBOOT REQUIRED <<<"
}

status() {
  echo "--- /proc/cmdline ---"; cat /proc/cmdline
  echo "--- isolated / nohz_full cpus ---"
  cat /sys/devices/system/cpu/isolated 2>/dev/null || echo "(isolcpus inactive)"
  cat /sys/devices/system/cpu/nohz_full 2>/dev/null || echo "(nohz_full inactive)"
  echo "--- systemd AllowedCPUs ---"; systemctl show system.slice -p AllowedCPUs; systemctl show user.slice -p AllowedCPUs
  echo "--- IRQ steering unit ---"; systemctl is-enabled rq1-fromdefault-irq-steer.service 2>/dev/null || echo "not installed"
  echo "--- IRQs still allowed outside cpu$KEEP ---"
  n=0; for f in /proc/irq/*/smp_affinity_list; do v=$(cat "$f" 2>/dev/null); [ "$v" != "$KEEP" ] && n=$((n+1)); done; echo "$n irq(s) with affinity != $KEEP"
  echo "--- THP / mitigations ---"; cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null; grep -o "mitigations=[a-z]*" /proc/cmdline || echo "mitigations: default (on)"
  echo "--- frequency ---"
  cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo "(governor not exposed)"
  echo "no_turbo=$(cat /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || echo n/a) boost=$(cat /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || echo n/a)"
  echo "cpu0 min/max: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq 2>/dev/null) / $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null)"
}

apply() {
  case "$LEVER" in
    isolcpus)    grub_add isolcpus  "isolcpus=$ISO" ;;
    nohz_full)   grub_add nohz_full "nohz_full=$ISO" ;;
    rcu_nocbs)   grub_add rcu_nocbs "rcu_nocbs=$ISO" ;;
    boot_params) grub_add boot_params "mitigations=off transparent_hugepage=never rcu_nocb_poll"
                 echo never > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true ;;
    systemd)
      mkdir -p "$(dirname "$DROP_SYS")" "$(dirname "$DROP_USR")"
      printf '[Slice]\nAllowedCPUs=%s\n' "$KEEP" > "$DROP_SYS"; printf '[Slice]\nAllowedCPUs=%s\n' "$KEEP" > "$DROP_USR"
      systemctl daemon-reload
      systemctl set-property system.slice AllowedCPUs="$KEEP"; systemctl set-property user.slice AllowedCPUs="$KEEP"
      echo "system.slice + user.slice clamped to cpu$KEEP" ;;
    irq_steer)
      for f in /proc/irq/*/smp_affinity_list; do echo "$KEEP" > "$f" 2>/dev/null || true; done
      cat > "$IRQ_UNIT" <<EOF
[Unit]
Description=RQ1_fromdefault -- steer all device IRQs onto cpu$KEEP at boot
After=multi-user.target
[Service]
Type=oneshot
ExecStart=/bin/bash -c 'for f in /proc/irq/*/smp_affinity_list; do echo $KEEP > "\$f" 2>/dev/null || true; done'
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF
      systemctl daemon-reload; systemctl enable --now rq1-fromdefault-irq-steer.service
      echo "IRQs steered onto cpu$KEEP now and at every boot" ;;
    freq_pin)
      for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > "$g" 2>/dev/null || true; done
      echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true
      echo 0 > /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || true
      for c in /sys/devices/system/cpu/cpu*/cpufreq; do
        [ -f "$c/scaling_min_freq" ] && [ -f "$c/cpuinfo_min_freq" ] && cat "$c/scaling_min_freq" > "$c/scaling_max_freq" 2>/dev/null || true
      done
      echo "frequency pinned (performance / no turbo / min=max). Deploy the agent WITHOUT SKIP_FREQ_PIN so it re-pins on restart." ;;
    *) echo "unknown lever '$LEVER'"; exit 2 ;;
  esac
}

restore() {
  case "$LEVER" in
    isolcpus|nohz_full|rcu_nocbs) grub_del "$LEVER" ;;
    boot_params) grub_del boot_params; echo always > /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true ;;
    systemd) rm -f "$DROP_SYS" "$DROP_USR"; systemctl daemon-reload
             systemctl set-property system.slice AllowedCPUs="" 2>/dev/null || true; systemctl set-property user.slice AllowedCPUs="" 2>/dev/null || true
             echo "systemd containment removed" ;;
    irq_steer) systemctl disable --now rq1-fromdefault-irq-steer.service 2>/dev/null || true; rm -f "$IRQ_UNIT"; systemctl daemon-reload
               echo "IRQ steering unit removed (existing affinity left as is; reboot to reset it)" ;;
    freq_pin) bash -c '
      avail=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null); d=$(echo "$avail" | awk "{print \$1}")
      case " $avail " in *" schedutil "*) d=schedutil;; *" ondemand "*) d=ondemand;; esac
      for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo "$d" > "$g" 2>/dev/null || true; done
      echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true; echo 1 > /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || true
      for c in /sys/devices/system/cpu/cpu*/cpufreq; do
        [ -f "$c/cpuinfo_max_freq" ] && cat "$c/cpuinfo_max_freq" > "$c/scaling_max_freq" 2>/dev/null || true
        [ -f "$c/cpuinfo_min_freq" ] && cat "$c/cpuinfo_min_freq" > "$c/scaling_min_freq" 2>/dev/null || true
      done; echo "governor reset to $d, turbo on, min/max unpinned"' ;;
    *) echo "unknown lever '$LEVER'"; exit 2 ;;
  esac
}
case "$MODE" in status) status;; apply) apply;; restore) restore;; *) echo "mode?"; exit 2;; esac
CORE
