#ifndef PERIODIC_H
#define PERIODIC_H

#include <stdint.h>

/*
 * Sleep until the absolute monotonic time `target_ns` (CLOCK_MONOTONIC,
 * TIMER_ABSTIME). Re-sleeps to the same absolute target on EINTR so signals
 * never cause schedule drift. Returns 0 on success or the clock_nanosleep
 * error code.
 */
int sleep_until_ns(uint64_t target_ns);

#endif /* PERIODIC_H */
