#ifndef THROTTLE_H
#define THROTTLE_H

#include <stdbool.h>
#include <stdint.h>

/*
 * Snapshot of the container's cgroup v2 cpu.stat throttling counters.
 *
 * `nr_throttled` / `throttled_usec` are non-zero only when CFS bandwidth
 * (cpu.max) throttling takes the container off-CPU despite runnable work. This
 * is an *in-guest* cause of missed supply (mechanism B), distinct from host
 * steal (mechanism A, see steal.h): together they let a deadline miss be
 * attributed to "the host descheduled the VM" vs "the kernel throttled us".
 *
 * Note: SCHED_DEADLINE budget exhaustion is NOT reflected here (cpu.stat tracks
 * CFS bandwidth only); for the rtdra arm this reader is mainly a control that
 * should read zero, while the vanilla arm may show throttling under cpu.max.
 */
typedef struct {
    uint64_t nr_throttled;   /* number of throttling events */
    uint64_t throttled_usec; /* cumulative throttled time (us) */
    bool ok;                 /* false if cpu.stat could not be read/parsed */
} throttle_sample_t;

/*
 * Read cgroup v2 cpu.stat. Defaults to "/sys/fs/cgroup/cpu.stat" (the
 * container's own cgroup root as seen from inside the container); override with
 * the KDL_CPU_STAT environment variable. Returns ok=false if the file is
 * absent or unparseable (e.g. cgroup v1, or no cpu controller).
 */
throttle_sample_t throttle_read(void);

/* Throttled CPU time (us) accrued between two snapshots. */
uint64_t throttle_us(throttle_sample_t before, throttle_sample_t after);

#endif /* THROTTLE_H */
