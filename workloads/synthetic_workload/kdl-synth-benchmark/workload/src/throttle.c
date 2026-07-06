#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "throttle.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

throttle_sample_t throttle_read(void) {
    throttle_sample_t s = {0, 0, false};

    const char *path = getenv("KDL_CPU_STAT");
    if (!path || !*path) {
        path = "/sys/fs/cgroup/cpu.stat";
    }

    FILE *f = fopen(path, "r");
    if (!f) {
        return s;
    }

    /*
     * cgroup v2 cpu.stat is a set of "key value" lines, e.g.
     *   usage_usec 12345
     *   nr_periods 10
     *   nr_throttled 2
     *   throttled_usec 3456
     * We only need the two throttling counters; order is not guaranteed.
     */
    char key[64];
    unsigned long long val;
    while (fscanf(f, "%63s %llu", key, &val) == 2) {
        if (strcmp(key, "nr_throttled") == 0) {
            s.nr_throttled = (uint64_t)val;
        } else if (strcmp(key, "throttled_usec") == 0) {
            s.throttled_usec = (uint64_t)val;
        }
    }
    fclose(f);

    s.ok = true;
    return s;
}

uint64_t throttle_us(throttle_sample_t before, throttle_sample_t after) {
    if (!before.ok || !after.ok || after.throttled_usec <= before.throttled_usec) {
        return 0;
    }
    return after.throttled_usec - before.throttled_usec;
}
