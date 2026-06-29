#include "periodic.h"

#include <errno.h>
#include <time.h>

int sleep_until_ns(uint64_t target_ns) {
    struct timespec ts;
    ts.tv_sec = (time_t)(target_ns / 1000000000ULL);
    ts.tv_nsec = (long)(target_ns % 1000000000ULL);

    int rc;
    do {
        /* Absolute-time release: a late wake-up does not shift later periods. */
        rc = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, NULL);
    } while (rc == EINTR);

    return rc;
}
