#!/usr/bin/env bash
# isolation-audit.sh — measure the IMPACT of OS-isolation hardening on cores
# 1-3 (not just whether config changed). Take one snapshot per stage, under
# any label you like, then compare any two stages afterward. Runs directly
# on the worker node (needs mpstat/gcc/taskset; hwlatdetect optional).
#
# Usage (3-stage example — vanilla node, after node-prep, after full hardening):
#   sudo bash isolation-audit.sh snapshot vanilla    # before node-prep at all
#   ... apply node-prep (freq pin + isolcpus/nohz_full/rcu_nocbs), reboot ...
#   sudo bash isolation-audit.sh snapshot nodeprep
#   ... apply the rest (systemd AllowedCPUs, IRQ steering, THP=never,
#       mitigations=off + reboot, SMT off) ...
#   sudo bash isolation-audit.sh snapshot hardened
#
#   bash isolation-audit.sh report vanilla nodeprep     # node-prep's own effect
#   bash isolation-audit.sh report nodeprep hardened    # the extra hardening's effect
#   bash isolation-audit.sh report vanilla hardened     # total effect
#
# Labels are free text — use whatever names make sense for your stages.
# `report` with no arguments defaults to comparing "before" vs "after".
#
# Env overrides:
#   WINDOW=60   seconds used for the IRQ/THP delta + mpstat average (default 60)
#   CORE=2      core the syscall microbenchmark runs on (default 2)
set -u
OUTDIR="/var/lib/rq1-isolation-audit"
WINDOW="${WINDOW:-60}"
CORE="${CORE:-2}"
mkdir -p "$OUTDIR"

irq_sum() {
  # sums interrupt counts on cores 1,2,3 (columns 3,4,5 -- col1=IRQ label, col2=CPU0)
  awk 'NR>1{for(i=3;i<=5;i++) if($i ~ /^[0-9]+$/) s[i]+=$i} END{printf "%d %d %d\n", s[3]+0, s[4]+0, s[5]+0}' /proc/interrupts
}

thp_sum() {
  awk -F': *' '/thp_fault_alloc|thp_collapse_alloc|compact_stall/{s+=$2} END{print s+0}' /proc/vmstat
}

hvs_count() {
  # Hyper-V synthetic timer interrupt count for the given core (0-indexed)
  local core="$1"
  grep "^HVS" /proc/interrupts | awk -v c="$core" '{print $(c+2)}'
}

build_syscall_bench() {
  cat > "$OUTDIR/.syscall_bench.c" <<'EOF'
#include <stdio.h>
#include <unistd.h>
#include <time.h>
int main(void) {
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (long i = 0; i < 1000000; i++) getpid();
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double us = (t1.tv_sec - t0.tv_sec) * 1e6 + (t1.tv_nsec - t0.tv_nsec) / 1e3;
    printf("%.4f\n", us / 1000000.0);
    return 0;
}
EOF
  gcc -O2 -o "$OUTDIR/.syscall_bench" "$OUTDIR/.syscall_bench.c" 2>/dev/null
}

do_snapshot() {
  local label="$1"
  local f="$OUTDIR/$label.env"
  echo "Snapshotting '$label'..."

  # --- action 1: nohz_full tick rate on $CORE (5s delta) ---
  local hvs0 hvs1 tick_rate
  hvs0=$(hvs_count "$CORE")
  sleep 5
  hvs1=$(hvs_count "$CORE")
  tick_rate=$(( (hvs1 - hvs0) / 5 ))

  # --- actions 2/3/4 share one $WINDOW-second observation ---
  local irq0 irq1 thp0 thp1 mp_tmp
  read -r irq0_1 irq0_2 irq0_3 <<< "$(irq_sum)"
  thp0=$(thp_sum)

  mp_tmp="$OUTDIR/.mpstat_tmp"
  if ! command -v mpstat >/dev/null 2>&1; then
    echo "installing sysstat for mpstat..."
    apt-get install -y sysstat >/dev/null 2>&1
  fi
  mpstat -P 1,2,3 1 "$WINDOW" > "$mp_tmp" 2>/dev/null

  read -r irq1_1 irq1_2 irq1_3 <<< "$(irq_sum)"
  thp1=$(thp_sum)

  local nonidle1 nonidle2 nonidle3
  nonidle1=$(awk '$1=="Average:" && $2=="1"{print 100-$NF}' "$mp_tmp")
  nonidle2=$(awk '$1=="Average:" && $2=="2"{print 100-$NF}' "$mp_tmp")
  nonidle3=$(awk '$1=="Average:" && $2=="3"{print 100-$NF}' "$mp_tmp")

  # --- action 5: syscall overhead microbenchmark ---
  build_syscall_bench
  local syscall_us
  syscall_us=$(taskset -c "$CORE" "$OUTDIR/.syscall_bench" 2>/dev/null)
  syscall_us="${syscall_us:-n/a}"

  # --- action 9: hwlatdetect (optional, needs rt-tests) ---
  local hwlat_max="n/a" hwlat_exceed="n/a"
  if command -v hwlatdetect >/dev/null 2>&1; then
    local hw_out
    hw_out=$(timeout 40 hwlatdetect --duration=30 2>&1)
    echo "$hw_out" > "$OUTDIR/$label.hwlatdetect.log"
    hwlat_max=$(echo "$hw_out" | grep -oP 'Max Latency:\s*\K[0-9]+' || echo "n/a")
    hwlat_exceed=$(echo "$hw_out" | grep -oP 'Samples exceeding threshold:\s*\K[0-9]+' || echo "n/a")
  else
    echo "hwlatdetect not installed (sudo apt install -y rt-tests) -- skipping action 9"
  fi

  # --- action 8: NUMA topology, informational only, no delta ---
  numactl --hardware > "$OUTDIR/$label.numactl.txt" 2>/dev/null || echo "numactl not available" > "$OUTDIR/$label.numactl.txt"

  {
    echo "TIMESTAMP=$(date -Is)"
    echo "CORE=$CORE"
    echo "WINDOW=$WINDOW"
    echo "TICK_RATE_PER_SEC=$tick_rate"
    echo "NONIDLE_PCT_CORE1=$nonidle1"
    echo "NONIDLE_PCT_CORE2=$nonidle2"
    echo "NONIDLE_PCT_CORE3=$nonidle3"
    echo "IRQ_DELTA_CORE1=$((irq1_1 - irq0_1))"
    echo "IRQ_DELTA_CORE2=$((irq1_2 - irq0_2))"
    echo "IRQ_DELTA_CORE3=$((irq1_3 - irq0_3))"
    echo "THP_DELTA=$((thp1 - thp0))"
    echo "SYSCALL_US_PER_CALL=$syscall_us"
    echo "HWLAT_MAX_US=$hwlat_max"
    echo "HWLAT_EXCEED_COUNT=$hwlat_exceed"
  } > "$f"

  echo "Saved to $f"
}

pct_change() {
  local b="$1" a="$2"
  awk -v b="$b" -v a="$a" 'BEGIN{
    if (b !~ /^-?[0-9.]+$/ || a !~ /^-?[0-9.]+$/ || b+0==0) { print "n/a"; exit }
    printf "%.1f%%", (a-b)/b*100
  }'
}

do_report() {
  local label_b="${1:-before}" label_a="${2:-after}"
  local bf="$OUTDIR/$label_b.env" af="$OUTDIR/$label_a.env"
  if [ ! -f "$bf" ] || [ ! -f "$af" ]; then
    echo "Need both $bf and $af -- run 'snapshot $label_b' and 'snapshot $label_a' first."
    exit 1
  fi
  eval "$(sed 's/^/B_/' "$bf")"
  eval "$(sed 's/^/A_/' "$af")"

  printf "\n| Metric | %s | %s | Change |\n" "$label_b" "$label_a"
  printf "|---|---|---|---|\n"
  printf "| nohz_full tick rate (HVS, /sec, core%s) | %s | %s | %s |\n" "$B_CORE" "$B_TICK_RATE_PER_SEC" "$A_TICK_RATE_PER_SEC" "$(pct_change "$B_TICK_RATE_PER_SEC" "$A_TICK_RATE_PER_SEC")"
  printf "| non-idle %% core1 (%ss avg) | %s | %s | %s |\n" "$B_WINDOW" "$B_NONIDLE_PCT_CORE1" "$A_NONIDLE_PCT_CORE1" "$(pct_change "$B_NONIDLE_PCT_CORE1" "$A_NONIDLE_PCT_CORE1")"
  printf "| non-idle %% core2 (%ss avg) | %s | %s | %s |\n" "$B_WINDOW" "$B_NONIDLE_PCT_CORE2" "$A_NONIDLE_PCT_CORE2" "$(pct_change "$B_NONIDLE_PCT_CORE2" "$A_NONIDLE_PCT_CORE2")"
  printf "| non-idle %% core3 (%ss avg) | %s | %s | %s |\n" "$B_WINDOW" "$B_NONIDLE_PCT_CORE3" "$A_NONIDLE_PCT_CORE3" "$(pct_change "$B_NONIDLE_PCT_CORE3" "$A_NONIDLE_PCT_CORE3")"
  printf "| IRQ count delta /%ss, core1 | %s | %s | %s |\n" "$B_WINDOW" "$B_IRQ_DELTA_CORE1" "$A_IRQ_DELTA_CORE1" "$(pct_change "$B_IRQ_DELTA_CORE1" "$A_IRQ_DELTA_CORE1")"
  printf "| IRQ count delta /%ss, core2 | %s | %s | %s |\n" "$B_WINDOW" "$B_IRQ_DELTA_CORE2" "$A_IRQ_DELTA_CORE2" "$(pct_change "$B_IRQ_DELTA_CORE2" "$A_IRQ_DELTA_CORE2")"
  printf "| IRQ count delta /%ss, core3 | %s | %s | %s |\n" "$B_WINDOW" "$B_IRQ_DELTA_CORE3" "$A_IRQ_DELTA_CORE3" "$(pct_change "$B_IRQ_DELTA_CORE3" "$A_IRQ_DELTA_CORE3")"
  printf "| THP/compaction events /%ss | %s | %s | %s |\n" "$B_WINDOW" "$B_THP_DELTA" "$A_THP_DELTA" "$(pct_change "$B_THP_DELTA" "$A_THP_DELTA")"
  printf "| syscall overhead (us/call, getpid, core%s) | %s | %s | %s |\n" "$B_CORE" "$B_SYSCALL_US_PER_CALL" "$A_SYSCALL_US_PER_CALL" "$(pct_change "$B_SYSCALL_US_PER_CALL" "$A_SYSCALL_US_PER_CALL")"
  printf "| hwlatdetect max latency (us) | %s | %s | %s |\n" "$B_HWLAT_MAX_US" "$A_HWLAT_MAX_US" "$(pct_change "$B_HWLAT_MAX_US" "$A_HWLAT_MAX_US")"
  printf "| hwlatdetect samples > threshold | %s | %s | %s |\n" "$B_HWLAT_EXCEED_COUNT" "$A_HWLAT_EXCEED_COUNT" "$(pct_change "$B_HWLAT_EXCEED_COUNT" "$A_HWLAT_EXCEED_COUNT")"
  echo
  echo "NUMA topology (informational, no before/after): $OUTDIR/before.numactl.txt"
  echo
  echo "Not covered by this script -- needs the k8s harness, run separately:"
  echo "  - action 6 (mlockall): /usr/bin/time -v against the probe image, major/minor"
  echo "    page faults, before vs after adding mlockall() + rebuild"
  echo "  - action 7 (SMT off) outcome: model1 cv / mid_job_preempt_us before vs after,"
  echo "    same seed/cell, via analysis_lib.py -- this script only confirms the"
  echo "    structural change (nproc, /sys/devices/system/cpu/isolated), not the outcome"
}

case "${1:-}" in
  snapshot)
    [ -n "${2:-}" ] || { echo "usage: $0 snapshot <label>"; exit 1; }
    do_snapshot "$2"
    ;;
  report)
    do_report "${2:-}" "${3:-}"
    ;;
  *)
    echo "usage: $0 snapshot <label> | report [label_a label_b]"
    exit 1
    ;;
esac
