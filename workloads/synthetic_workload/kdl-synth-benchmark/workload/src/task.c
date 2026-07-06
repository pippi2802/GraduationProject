#include "task.h"

#include "calib.h"
#include "metrics.h"
#include "periodic.h"
#include "steal.h"
#include "throttle.h"
#include "timing.h"

#include <sched.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

/* Set by the main thread's signal handler to request a clean stop. */
extern volatile int g_stop;

const char *sched_policy_name(int policy) {
    switch (policy) {
    case SCHED_OTHER: return "SCHED_OTHER (CFS)";
    case SCHED_FIFO:  return "SCHED_FIFO (RT)";
    case SCHED_RR:    return "SCHED_RR (RT)";
#ifdef SCHED_BATCH
    case SCHED_BATCH: return "SCHED_BATCH";
#endif
#ifdef SCHED_IDLE
    case SCHED_IDLE:  return "SCHED_IDLE";
#endif
#ifdef SCHED_DEADLINE
    case SCHED_DEADLINE: return "SCHED_DEADLINE (EDF)";
#endif
    default: return "UNKNOWN";
    }
}

void print_sched_state(const char *who) {
    int policy = sched_getscheduler(0);

    struct sched_param sp;
    memset(&sp, 0, sizeof(sp));
    sched_getparam(0, &sp);

    char cpus[256];
    cpus[0] = '\0';
    cpu_set_t set;
    CPU_ZERO(&set);
    if (sched_getaffinity(0, sizeof(set), &set) == 0) {
        size_t off = 0;
        for (int cpu = 0; cpu < CPU_SETSIZE && off < sizeof(cpus) - 8; cpu++) {
            if (CPU_ISSET(cpu, &set)) {
                off += (size_t)snprintf(cpus + off, sizeof(cpus) - off, "%d,", cpu);
            }
        }
        if (off > 0) {
            cpus[off - 1] = '\0'; /* trim trailing comma */
        }
    }

    fprintf(stderr, "[sched] %-14s policy=%-20s priority=%d affinity=[%s] tid=%ld\n",
            who, sched_policy_name(policy < 0 ? -1 : policy), sp.sched_priority,
            cpus, (long)syscall(SYS_gettid));
}

void *task_thread(void *arg) {
    task_arg_t *ta = (task_arg_t *)arg;

    char who[24];
    snprintf(who, sizeof(who), "task %d", ta->id);
    print_sched_state(who);

    const uint64_t period_ns = ta->t_us * 1000ULL;
    const uint64_t deadline_ns = ta->d_us * 1000ULL;
    const uint64_t total = ta->jobs + ta->warmup;

    uint64_t next = ta->start_at_ns; /* absolute release time of current job */

    for (uint64_t j = 0; j < total && !g_stop; j++) {
        sleep_until_ns(next);

        /*
         * Attribution samples bracket the whole active phase of the job. They
         * are read outside the cpu0..cpu1 / t0..t1 window so their overhead does
         * not pollute exec_time / response_time. Zero-cost when attr is off.
         */
        const steal_sample_t js0 =
            ta->attr ? steal_read() : (steal_sample_t){0, 0, false};
        const throttle_sample_t jt0 =
            ta->attr ? throttle_read() : (throttle_sample_t){0, 0, false};

        const uint64_t release = next;
        const uint64_t cpu0 = now_ns(CLOCK_THREAD_CPUTIME_ID);
        const uint64_t t0 = now_ns(CLOCK_MONOTONIC);

        burn_cpu(ta->c_us, ta->iters_per_us);

        const uint64_t cpu1 = now_ns(CLOCK_THREAD_CPUTIME_ID);
        const uint64_t t1 = now_ns(CLOCK_MONOTONIC);

        const steal_sample_t js1 =
            ta->attr ? steal_read() : (steal_sample_t){0, 0, false};
        const throttle_sample_t jt1 =
            ta->attr ? throttle_read() : (throttle_sample_t){0, 0, false};
        const int cpu_id = sched_getcpu();

        next += period_ns; /* absolute, no drift */

        if (j < ta->warmup) {
            continue; /* discard warmup jobs */
        }

        const uint64_t exec_us = (cpu1 - cpu0) / 1000ULL;
        const uint64_t resp_us = (t1 - release) / 1000ULL;
        /* Wall time spent inside the burn (release-to-start + on/off CPU). */
        const uint64_t burn_wall_us = (t1 - t0) / 1000ULL;
        const uint64_t deadline_abs = release + deadline_ns;
        const bool miss = t1 > deadline_abs;
        const uint64_t tard_us = miss ? (t1 - deadline_abs) / 1000ULL : 0;
        /* Supply signals (G1): time ready but off-CPU. */
        const uint64_t wait_us = resp_us > exec_us ? resp_us - exec_us : 0;
        const uint64_t preempt_us = burn_wall_us > exec_us ? burn_wall_us - exec_us : 0;
        /* Cause covariates: host steal (A) vs in-guest CFS throttle (B). */
        const uint64_t job_steal_us = ta->attr ? steal_us(js0, js1) : 0;
        const uint64_t job_throttled_us = ta->attr ? throttle_us(jt0, jt1) : 0;

        job_record_t rec = {
            .task_id = ta->id,
            .job_index = j,
            .release_ts_ns = release - ta->epoch_ns,
            .start_ts_ns = t0 - ta->epoch_ns,
            .completion_ts_ns = t1 - ta->epoch_ns,
            .exec_time_us = exec_us,
            .response_time_us = resp_us,
            .wait_time_us = wait_us,
            .preempt_us = preempt_us,
            .steal_us = job_steal_us,
            .throttled_us = job_throttled_us,
            .cpu_id = cpu_id,
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
