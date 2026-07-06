#include "metrics.h"

#include <pthread.h>
#include <stdio.h>

static FILE *g_fp = NULL;
static metrics_labels_t g_labels;
static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;

int metrics_open(const char *path, const metrics_labels_t *labels) {
    g_labels = *labels;
    g_fp = fopen(path, "w");
    if (!g_fp) {
        return -1;
    }
    /* Fully buffered; we flush explicitly and on signal. */
    setvbuf(g_fp, NULL, _IOFBF, 1 << 16);
    return 0;
}

void metrics_write(const job_record_t *r) {
    if (!g_fp) {
        return;
    }
    pthread_mutex_lock(&g_lock);
    fprintf(g_fp,
        "{\"record\":\"job\",\"run_id\":\"%s\",\"mode\":\"%s\",\"taskset_id\":\"%s\","
        "\"task_id\":%d,\"job_index\":%llu,"
        "\"release_ts_ns\":%llu,\"start_ts_ns\":%llu,\"completion_ts_ns\":%llu,"
        "\"exec_time_us\":%llu,\"response_time_us\":%llu,"
        "\"wait_time_us\":%llu,\"preempt_us\":%llu,"
        "\"steal_us\":%llu,\"throttled_us\":%llu,\"cpu_id\":%d,"
        "\"target_c_us\":%llu,\"period_t_us\":%llu,\"deadline_us\":%llu,"
        "\"overrun\":%s,\"deadline_miss\":%s,\"tardiness_us\":%llu,"
        "\"budget_q_us\":%llu,\"period_p_us\":%llu,\"cores_m\":%d,"
        "\"util\":%.6f,\"n_tasks\":%d,\"interference\":\"%s\","
        "\"node\":\"%s\",\"kernel\":\"%s\"}\n",
        g_labels.run_id, g_labels.mode, g_labels.taskset_id,
        r->task_id, (unsigned long long)r->job_index,
        (unsigned long long)r->release_ts_ns,
        (unsigned long long)r->start_ts_ns,
        (unsigned long long)r->completion_ts_ns,
        (unsigned long long)r->exec_time_us,
        (unsigned long long)r->response_time_us,
        (unsigned long long)r->wait_time_us,
        (unsigned long long)r->preempt_us,
        (unsigned long long)r->steal_us,
        (unsigned long long)r->throttled_us,
        r->cpu_id,
        (unsigned long long)r->target_c_us,
        (unsigned long long)r->period_t_us,
        (unsigned long long)r->deadline_us,
        r->overrun ? "true" : "false",
        r->deadline_miss ? "true" : "false",
        (unsigned long long)r->tardiness_us,
        (unsigned long long)g_labels.budget_q_us,
        (unsigned long long)g_labels.period_p_us,
        g_labels.cores_m, g_labels.util, g_labels.n_tasks,
        g_labels.interference, g_labels.node, g_labels.kernel);
    pthread_mutex_unlock(&g_lock);
}

void metrics_write_summary(const metrics_summary_t *s) {
    if (!g_fp) {
        return;
    }
    pthread_mutex_lock(&g_lock);
    fprintf(g_fp,
        "{\"record\":\"summary\",\"run_id\":\"%s\",\"mode\":\"%s\","
        "\"taskset_id\":\"%s\",\"steal_pct\":%.6f,\"steal_us\":%llu,"
        "\"throttled_us\":%llu,\"nr_throttled\":%llu,"
        "\"wall_us\":%llu,\"iters_per_us\":%.6f,"
        "\"budget_q_us\":%llu,\"period_p_us\":%llu,\"cores_m\":%d,"
        "\"util\":%.6f,\"n_tasks\":%d,\"interference\":\"%s\","
        "\"node\":\"%s\",\"kernel\":\"%s\"}\n",
        g_labels.run_id, g_labels.mode, g_labels.taskset_id,
        s->steal_pct, (unsigned long long)s->steal_us,
        (unsigned long long)s->throttled_us, (unsigned long long)s->nr_throttled,
        (unsigned long long)s->wall_us, s->iters_per_us,
        (unsigned long long)g_labels.budget_q_us,
        (unsigned long long)g_labels.period_p_us,
        g_labels.cores_m, g_labels.util, s->n_tasks,
        g_labels.interference, g_labels.node, g_labels.kernel);
    pthread_mutex_unlock(&g_lock);
}

void metrics_flush(void) {
    if (g_fp) {
        fflush(g_fp);
    }
}

void metrics_close(void) {
    if (g_fp) {
        fflush(g_fp);
        fclose(g_fp);
        g_fp = NULL;
    }
}
