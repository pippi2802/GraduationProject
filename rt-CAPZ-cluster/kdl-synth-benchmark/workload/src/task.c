#include "task.h"

#include "calib.h"
#include "metrics.h"
#include "periodic.h"
#include "timing.h"

#include <time.h>

/* Set by the main thread's signal handler to request a clean stop. */
extern volatile int g_stop;

void *task_thread(void *arg) {
    task_arg_t *ta = (task_arg_t *)arg;

    const uint64_t period_ns = ta->t_us * 1000ULL;
    const uint64_t deadline_ns = ta->d_us * 1000ULL;
    const uint64_t total = ta->jobs + ta->warmup;

    uint64_t next = ta->start_at_ns; /* absolute release time of current job */

    for (uint64_t j = 0; j < total && !g_stop; j++) {
        sleep_until_ns(next);

        const uint64_t release = next;
        const uint64_t cpu0 = now_ns(CLOCK_THREAD_CPUTIME_ID);
        const uint64_t t0 = now_ns(CLOCK_MONOTONIC);

        burn_cpu(ta->c_us, ta->iters_per_us);

        const uint64_t cpu1 = now_ns(CLOCK_THREAD_CPUTIME_ID);
        const uint64_t t1 = now_ns(CLOCK_MONOTONIC);

        next += period_ns; /* absolute, no drift */

        if (j < ta->warmup) {
            continue; /* discard warmup jobs */
        }

        const uint64_t exec_us = (cpu1 - cpu0) / 1000ULL;
        const uint64_t resp_us = (t1 - release) / 1000ULL;
        const uint64_t deadline_abs = release + deadline_ns;
        const bool miss = t1 > deadline_abs;
        const uint64_t tard_us = miss ? (t1 - deadline_abs) / 1000ULL : 0;

        job_record_t rec = {
            .task_id = ta->id,
            .job_index = j,
            .release_ts_ns = release - ta->epoch_ns,
            .start_ts_ns = t0 - ta->epoch_ns,
            .completion_ts_ns = t1 - ta->epoch_ns,
            .exec_time_us = exec_us,
            .response_time_us = resp_us,
            .target_c_us = ta->c_us,
            .period_t_us = ta->t_us,
            .deadline_us = ta->d_us,
            .overrun = exec_us > ta->c_us,
            .deadline_miss = miss,
            .tardiness_us = tard_us,
        };
        metrics_write(&rec);
    }
    return NULL;
}
