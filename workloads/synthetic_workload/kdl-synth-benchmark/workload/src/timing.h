#ifndef TIMING_H
#define TIMING_H

#include <stdint.h>
#include <time.h>

/* Convert a struct timespec to nanoseconds (64-bit). */
static inline uint64_t ts_to_ns(const struct timespec *ts) {
    return (uint64_t)ts->tv_sec * 1000000000ULL + (uint64_t)ts->tv_nsec;
}

/* Read the given clock and return nanoseconds since its epoch. */
uint64_t now_ns(clockid_t clk);

#endif /* TIMING_H */
