#ifndef CALIB_H
#define CALIB_H

#include <stdint.h>

/*
 * Calibrate the busy-loop: measure how many work-loop iterations correspond
 * to one microsecond of *thread CPU time* (CLOCK_THREAD_CPUTIME_ID).
 * Returns iterations-per-microsecond (double).
 */
double calibrate_iters_per_us(void);

/*
 * Consume `c_us` microseconds of *thread CPU time*. The loop re-checks
 * CLOCK_THREAD_CPUTIME_ID every chunk and stops once the budget is spent,
 * so it is robust to cloud frequency drift / CPU steal. The arithmetic is
 * protected from the optimizer via a volatile sink.
 */
void burn_cpu(uint64_t c_us, double iters_per_us);

#endif /* CALIB_H */
