// rt_periodic.c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <time.h>
#include <stdlib.h>
#include <unistd.h>

static inline int64_t ns_now(clockid_t clk) {
    struct timespec ts;
    clock_gettime(clk, &ts);
    return (int64_t)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static inline void ns_to_timespec(int64_t ns, struct timespec *ts) {
    ts->tv_sec = ns / 1000000000LL;
    ts->tv_nsec = ns % 1000000000LL;
}

int main(int argc, char **argv) {
    // Defaults: 10ms period, 2ms CPU runtime, 20000 iterations
    int64_t period_us  = (argc > 1) ? atoll(argv[1]) : 10000;
    int64_t runtime_us = (argc > 2) ? atoll(argv[2]) : 2000;
    int64_t iters      = (argc > 3) ? atoll(argv[3]) : 20000;

    const int64_t period_ns  = period_us * 1000LL;
    const int64_t runtime_ns = runtime_us * 1000LL;

    // CSV header
    printf("i,release_ns,start_ns,finish_ns,response_us,exec_cpu_us,miss\n");
    fflush(stdout);

    int64_t release = ns_now(CLOCK_MONOTONIC);
    // align to next period boundary
    release = ((release / period_ns) + 1) * period_ns;

    for (int64_t i = 0; i < iters; i++) {
        struct timespec ts;
        ns_to_timespec(release, &ts);

        // Sleep until absolute release time
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, NULL); // high-res sleep 【2-83c1ef】

        int64_t start = ns_now(CLOCK_MONOTONIC);

        // Burn CPU for runtime_ns measured as thread CPU time (only counts when running)
        int64_t cpu_start = ns_now(CLOCK_THREAD_CPUTIME_ID);
        while (ns_now(CLOCK_THREAD_CPUTIME_ID) - cpu_start < runtime_ns) {
            asm volatile("" ::: "memory"); // prevent over-optimisation
        }
        int64_t cpu_end = ns_now(CLOCK_THREAD_CPUTIME_ID);

        int64_t finish = ns_now(CLOCK_MONOTONIC);

        int miss = (finish > (release + period_ns)) ? 1 : 0;
        double response_us = (finish - release) / 1000.0;
        double exec_cpu_us = (cpu_end - cpu_start) / 1000.0;

        printf("%lld,%lld,%lld,%lld,%.3f,%.3f,%d\n",
               (long long)i,
               (long long)release, (long long)start, (long long)finish,
               response_us, exec_cpu_us, miss);
        fflush(stdout);

        release += period_ns;
    }
    return 0;
}