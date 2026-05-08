// rt_multi_periodic.c
// Spawns N periodic threads inside a single process. Each thread writes its
// own per-invocation CSV to $OUT_DIR/<prefix>_task<idx>.csv.
//
// Task spec is given as repeated CLI args:
//   <period_us>:<runtime_us>:<iters>
// e.g.:
//   rt_multi_periodic /out cA 20000:5000:500 50000:15000:200 100000:25000:100
//
// CSV columns (per task):
//   i,release_ns,start_ns,finish_ns,response_us,exec_cpu_us,miss
//
// "miss" = 1 when finish > release + period (deadline = release + period).
// We use CLOCK_MONOTONIC for release/response and CLOCK_THREAD_CPUTIME_ID
// to bound CPU work performed inside each invocation.

#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <pthread.h>
#include <unistd.h>
#include <errno.h>
#include <sys/stat.h>

typedef struct {
    int      idx;
    int64_t  period_us;
    int64_t  runtime_us;
    int64_t  iters;
    char     out_path[512];
    int64_t  start_release_ns; // shared aligned start
} task_arg_t;

static inline int64_t ns_now(clockid_t clk) {
    struct timespec ts;
    clock_gettime(clk, &ts);
    return (int64_t)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static inline void ns_to_timespec(int64_t ns, struct timespec *ts) {
    ts->tv_sec  = ns / 1000000000LL;
    ts->tv_nsec = ns % 1000000000LL;
}

static void *task_main(void *p) {
    task_arg_t *a = (task_arg_t *)p;
    const int64_t period_ns  = a->period_us  * 1000LL;
    const int64_t runtime_ns = a->runtime_us * 1000LL;

    FILE *f = fopen(a->out_path, "w");
    if (!f) {
        fprintf(stderr, "task %d: cannot open %s: %s\n",
                a->idx, a->out_path, strerror(errno));
        return NULL;
    }
    fprintf(f, "i,release_ns,start_ns,finish_ns,response_us,exec_cpu_us,miss\n");
    fflush(f);

    int64_t release = a->start_release_ns;

    for (int64_t i = 0; i < a->iters; i++) {
        struct timespec ts;
        ns_to_timespec(release, &ts);
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, NULL);

        int64_t start = ns_now(CLOCK_MONOTONIC);

        int64_t cpu_start = ns_now(CLOCK_THREAD_CPUTIME_ID);
        while (ns_now(CLOCK_THREAD_CPUTIME_ID) - cpu_start < runtime_ns) {
            asm volatile("" ::: "memory");
        }
        int64_t cpu_end = ns_now(CLOCK_THREAD_CPUTIME_ID);

        int64_t finish = ns_now(CLOCK_MONOTONIC);
        int miss = (finish > (release + period_ns)) ? 1 : 0;
        double response_us = (finish - release) / 1000.0;
        double exec_cpu_us = (cpu_end - cpu_start) / 1000.0;

        fprintf(f, "%lld,%lld,%lld,%lld,%.3f,%.3f,%d\n",
                (long long)i,
                (long long)release, (long long)start, (long long)finish,
                response_us, exec_cpu_us, miss);

        release += period_ns;
    }
    fflush(f);
    fclose(f);
    return NULL;
}

static int parse_spec(const char *s, int64_t *period, int64_t *runtime, int64_t *iters) {
    return sscanf(s, "%lld:%lld:%lld",
                  (long long *)period, (long long *)runtime, (long long *)iters) == 3;
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr,
            "usage: %s <out_dir> <prefix> <p_us:c_us:iters> [<p:c:n> ...]\n", argv[0]);
        return 2;
    }
    const char *out_dir = argv[1];
    const char *prefix  = argv[2];
    int n = argc - 3;

    if (mkdir(out_dir, 0777) < 0 && errno != EEXIST) {
        fprintf(stderr, "mkdir %s: %s\n", out_dir, strerror(errno));
        return 1;
    }

    task_arg_t *args = calloc(n, sizeof(*args));
    pthread_t  *tids = calloc(n, sizeof(*tids));
    if (!args || !tids) { perror("calloc"); return 1; }

    // Align all tasks to the same release time so contention starts together.
    int64_t now = ns_now(CLOCK_MONOTONIC);
    int64_t aligned_start = ((now / 1000000000LL) + 2) * 1000000000LL; // +2s

    for (int i = 0; i < n; i++) {
        if (!parse_spec(argv[3 + i],
                        &args[i].period_us,
                        &args[i].runtime_us,
                        &args[i].iters)) {
            fprintf(stderr, "bad spec '%s' (want p_us:c_us:iters)\n", argv[3 + i]);
            return 2;
        }
        args[i].idx = i;
        args[i].start_release_ns = aligned_start;
        snprintf(args[i].out_path, sizeof(args[i].out_path),
                 "%s/%s_task%d.csv", out_dir, prefix, i);
        printf("task %d: period=%lld us, runtime=%lld us, iters=%lld -> %s\n",
               i,
               (long long)args[i].period_us,
               (long long)args[i].runtime_us,
               (long long)args[i].iters,
               args[i].out_path);
    }
    fflush(stdout);

    for (int i = 0; i < n; i++) {
        if (pthread_create(&tids[i], NULL, task_main, &args[i]) != 0) {
            perror("pthread_create");
            return 1;
        }
    }
    for (int i = 0; i < n; i++) {
        pthread_join(tids[i], NULL);
    }

    free(args);
    free(tids);
    return 0;
}
