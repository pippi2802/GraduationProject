#ifndef STEAL_H
#define STEAL_H

#include <stdbool.h>
#include <stdint.h>

/*
 * A snapshot of the guest-visible CPU time breakdown from /proc/stat
 * (aggregate "cpu" line), in jiffies summed across all vCPUs.
 *
 * `steal` is time the vCPU was runnable but the hypervisor scheduled a
 * different guest instead -- i.e. CPU supply the guest expected but did not
 * receive. Comparing two snapshots over a run yields the fraction of CPU time
 * stolen by the host, the primary cloud cause of supply-guarantee (G1) breakage.
 */
typedef struct {
    uint64_t steal; /* jiffies stolen by the hypervisor */
    uint64_t total; /* jiffies across all states (sum of every field) */
    bool ok;        /* false if /proc/stat could not be read/parsed */
} steal_sample_t;

/* Read the aggregate "cpu" line of /proc/stat. */
steal_sample_t steal_read(void);

/* Percentage of CPU time stolen between two snapshots, in [0, 100]. */
double steal_pct(steal_sample_t before, steal_sample_t after);

/* Stolen CPU time in microseconds between two snapshots (uses _SC_CLK_TCK). */
uint64_t steal_us(steal_sample_t before, steal_sample_t after);

#endif /* STEAL_H */
