#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include "calib.h"
#include "metrics.h"
#include "task.h"
#include "timing.h"

#include <getopt.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define MAX_TASKS 64

/* Stop flag, observed by every task thread. */
volatile int g_stop = 0;

static void on_signal(int sig) {
    (void)sig;
    g_stop = 1;
    /* Make a kubectl delete still yield complete data. */
    metrics_flush();
}

/* Read an entire file into a NUL-terminated buffer (caller frees). */
static char *read_file(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        return NULL;
    }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    if (n < 0) {
        fclose(f);
        return NULL;
    }
    fseek(f, 0, SEEK_SET);
    char *buf = malloc((size_t)n + 1);
    if (!buf) {
        fclose(f);
        return NULL;
    }
    size_t rd = fread(buf, 1, (size_t)n, f);
    buf[rd] = '\0';
    fclose(f);
    return buf;
}

/* Extract an integer value for `key` within the object substring [obj, end). */
static int obj_get_int(const char *obj, const char *end, const char *key, long *out) {
    char pat[64];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *p = strstr(obj, pat);
    if (!p || p >= end) {
        return -1;
    }
    p += strlen(pat);
    while (p < end && (*p == ' ' || *p == ':' || *p == '\t')) {
        p++;
    }
    *out = strtol(p, NULL, 10);
    return 0;
}

/*
 * Minimal taskset JSON parser. Expects an array of flat objects:
 *   [{ "id":0, "c_us":4200, "t_us":33000 }, ...]
 * Only libc is used; nesting is not supported (not needed here).
 */
static int parse_taskset(const char *json, task_arg_t *tasks, int max) {
    int count = 0;
    const char *p = json;
    while ((p = strchr(p, '{')) != NULL && count < max) {
        const char *end = strchr(p, '}');
        if (!end) {
            break;
        }
        long id = count, c_us = 0, t_us = 0;
        obj_get_int(p, end, "id", &id);
        obj_get_int(p, end, "c_us", &c_us);
        obj_get_int(p, end, "t_us", &t_us);
        if (t_us > 0 && c_us > 0) {
            tasks[count].id = (int)id;
            tasks[count].c_us = (uint64_t)c_us;
            tasks[count].t_us = (uint64_t)t_us;
            tasks[count].d_us = (uint64_t)t_us;
            count++;
        }
        p = end + 1;
    }
    return count;
}

static void usage(const char *prog) {
    fprintf(stderr,
        "usage: %s --taskset FILE [options]\n"
        "  --taskset FILE       taskset JSON (required)\n"
        "  --jobs N             measured jobs per task (default 1000)\n"
        "  --warmup N           warmup jobs to discard (default 20)\n"
        "  --out FILE           metrics JSONL output (default metrics.jsonl)\n"
        "  --run-id S           run identifier label\n"
        "  --taskset-id S       taskset identifier label\n"
        "  --mode S             rtdra|vanilla (label)\n"
        "  --budget-q-us N      Q label (us)\n"
        "  --period-p-us N      P label (us)\n"
        "  --cores-m N          m label (cores)\n"
        "  --util F             utilisation label\n"
        "  --interference S     none|on (label)\n"
        "  --node S             node label\n"
        "  --kernel S           kernel label\n",
        prog);
}

int main(int argc, char **argv) {
    const char *taskset_path = NULL;
    const char *out_path = "metrics.jsonl";
    const char *run_id = "run";
    const char *taskset_id = "set";
    const char *mode = "rtdra";
    const char *interference = "none";
    const char *node = "unknown";
    const char *kernel = "unknown";
    uint64_t jobs = 1000, warmup = 20;
    uint64_t budget_q_us = 0, period_p_us = 0;
    int cores_m = 0;
    double util = 0.0;

    static struct option opts[] = {
        {"taskset", required_argument, 0, 't'},
        {"jobs", required_argument, 0, 'j'},
        {"warmup", required_argument, 0, 'w'},
        {"out", required_argument, 0, 'o'},
        {"run-id", required_argument, 0, 'r'},
        {"taskset-id", required_argument, 0, 'I'},
        {"mode", required_argument, 0, 'm'},
        {"budget-q-us", required_argument, 0, 'Q'},
        {"period-p-us", required_argument, 0, 'P'},
        {"cores-m", required_argument, 0, 'M'},
        {"util", required_argument, 0, 'U'},
        {"interference", required_argument, 0, 'i'},
        {"node", required_argument, 0, 'n'},
        {"kernel", required_argument, 0, 'k'},
        {"help", no_argument, 0, 'h'},
        {0, 0, 0, 0}};

    int c, idx;
    while ((c = getopt_long(argc, argv, "h", opts, &idx)) != -1) {
        switch (c) {
        case 't': taskset_path = optarg; break;
        case 'j': jobs = strtoull(optarg, NULL, 10); break;
        case 'w': warmup = strtoull(optarg, NULL, 10); break;
        case 'o': out_path = optarg; break;
        case 'r': run_id = optarg; break;
        case 'I': taskset_id = optarg; break;
        case 'm': mode = optarg; break;
        case 'Q': budget_q_us = strtoull(optarg, NULL, 10); break;
        case 'P': period_p_us = strtoull(optarg, NULL, 10); break;
        case 'M': cores_m = atoi(optarg); break;
        case 'U': util = atof(optarg); break;
        case 'i': interference = optarg; break;
        case 'n': node = optarg; break;
        case 'k': kernel = optarg; break;
        case 'h': usage(argv[0]); return 0;
        default: usage(argv[0]); return 2;
        }
    }

    if (!taskset_path) {
        usage(argv[0]);
        return 2;
    }

    char *json = read_file(taskset_path);
    if (!json) {
        fprintf(stderr, "error: cannot read taskset %s\n", taskset_path);
        return 1;
    }

    task_arg_t tasks[MAX_TASKS];
    memset(tasks, 0, sizeof(tasks));
    int n = parse_taskset(json, tasks, MAX_TASKS);
    free(json);
    if (n <= 0) {
        fprintf(stderr, "error: no tasks parsed from %s\n", taskset_path);
        return 1;
    }

    /* Install signal handlers for clean shutdown + flush. */
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_signal;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);

    fprintf(stderr, "calibrating busy-loop...\n");
    double iters_per_us = calibrate_iters_per_us();
    fprintf(stderr, "calibration: %.2f iters/us, %d tasks, %llu+%llu jobs\n",
            iters_per_us, n, (unsigned long long)warmup, (unsigned long long)jobs);

    metrics_labels_t labels = {
        .run_id = run_id,
        .mode = mode,
        .taskset_id = taskset_id,
        .budget_q_us = budget_q_us,
        .period_p_us = period_p_us,
        .cores_m = cores_m,
        .util = util,
        .n_tasks = n,
        .interference = interference,
        .node = node,
        .kernel = kernel,
    };
    if (metrics_open(out_path, &labels) != 0) {
        fprintf(stderr, "error: cannot open output %s\n", out_path);
        return 1;
    }

    const uint64_t epoch = now_ns(CLOCK_MONOTONIC);
    /* Start all tasks together, shortly in the future. */
    const uint64_t start_at = epoch + 100ULL * 1000000ULL; /* +100 ms */

    pthread_t th[MAX_TASKS];
    for (int i = 0; i < n; i++) {
        tasks[i].jobs = jobs;
        tasks[i].warmup = warmup;
        tasks[i].iters_per_us = iters_per_us;
        tasks[i].epoch_ns = epoch;
        tasks[i].start_at_ns = start_at;
        if (pthread_create(&th[i], NULL, task_thread, &tasks[i]) != 0) {
            fprintf(stderr, "error: pthread_create failed for task %d\n", i);
            g_stop = 1;
            break;
        }
    }

    for (int i = 0; i < n; i++) {
        pthread_join(th[i], NULL);
    }

    metrics_close();
    fprintf(stderr, "done: wrote %s\n", out_path);
    return 0;
}
