#include "calib.h"
#include "timing.h"

#include <time.h>

/*
 * Volatile sink: the result of the busy loop is stored here so that the
 * compiler cannot prove the arithmetic is dead and optimize it away, even
 * at -O2/-O3.
 */
static volatile double g_sink;

/*
 * A unit of pure-CPU arithmetic work. No I/O, no syscalls. `iters` controls
 * the chunk size between clock re-checks.
 */
static inline double work_chunk(double acc, long iters) {
    for (long k = 0; k < iters; k++) {
        acc = acc * 1.0000001 + 1.0;
        acc = acc - 0.5;
    }
    return acc;
}

double calibrate_iters_per_us(void) {
    const uint64_t target_ns = 50000ULL * 1000ULL; /* 50 ms calibration window */
    uint64_t iters = 0;
    double acc = 1.0;

    const uint64_t start = now_ns(CLOCK_THREAD_CPUTIME_ID);
    uint64_t elapsed = 0;
    while (elapsed < target_ns) {
        acc = work_chunk(acc, 2000);
        iters += 2000;
        elapsed = now_ns(CLOCK_THREAD_CPUTIME_ID) - start;
    }
    g_sink = acc;

    double us = (double)elapsed / 1000.0;
    if (us < 1.0) {
        us = 1.0;
    }
    return (double)iters / us;
}

void burn_cpu(uint64_t c_us, double iters_per_us) {
    const uint64_t start = now_ns(CLOCK_THREAD_CPUTIME_ID);
    const uint64_t target_ns = c_us * 1000ULL;

    /* Re-check the clock roughly every ~5 us of work. */
    long chunk = (long)(iters_per_us * 5.0);
    if (chunk < 1) {
        chunk = 1;
    }

    double acc = 1.0;
    for (;;) {
        uint64_t elapsed = now_ns(CLOCK_THREAD_CPUTIME_ID) - start;
        if (elapsed >= target_ns) {
            break;
        }
        acc = work_chunk(acc, chunk);
    }
    g_sink = acc;
}
