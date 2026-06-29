#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "steal.h"

#include <stdio.h>
#include <unistd.h>

steal_sample_t steal_read(void) {
    steal_sample_t s = {0, 0, false};

    FILE *f = fopen("/proc/stat", "r");
    if (!f) {
        return s;
    }

    /*
     * First line: "cpu  user nice system idle iowait irq softirq steal guest
     * guest_nice". steal is the 8th value; total is the sum of all values.
     */
    char label[16];
    uint64_t v[10] = {0};
    int got = fscanf(f, "%15s %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu",
                     label,
                     (unsigned long long *)&v[0], (unsigned long long *)&v[1],
                     (unsigned long long *)&v[2], (unsigned long long *)&v[3],
                     (unsigned long long *)&v[4], (unsigned long long *)&v[5],
                     (unsigned long long *)&v[6], (unsigned long long *)&v[7],
                     (unsigned long long *)&v[8], (unsigned long long *)&v[9]);
    fclose(f);

    /* Need at least the steal field (index 7 -> 8 numeric conversions + label). */
    if (got < 9) {
        return s;
    }

    uint64_t total = 0;
    for (int i = 0; i < 10; i++) {
        total += v[i];
    }
    s.steal = v[7];
    s.total = total;
    s.ok = true;
    return s;
}

double steal_pct(steal_sample_t before, steal_sample_t after) {
    if (!before.ok || !after.ok || after.total <= before.total) {
        return 0.0;
    }
    uint64_t d_steal = after.steal - before.steal;
    uint64_t d_total = after.total - before.total;
    if (d_total == 0) {
        return 0.0;
    }
    return 100.0 * (double)d_steal / (double)d_total;
}

uint64_t steal_us(steal_sample_t before, steal_sample_t after) {
    if (!before.ok || !after.ok || after.steal <= before.steal) {
        return 0;
    }
    long hz = sysconf(_SC_CLK_TCK);
    if (hz <= 0) {
        hz = 100;
    }
    uint64_t d_steal = after.steal - before.steal;
    return (d_steal * 1000000ULL) / (uint64_t)hz;
}
