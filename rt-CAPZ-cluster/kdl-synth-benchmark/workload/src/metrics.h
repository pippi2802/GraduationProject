#ifndef METRICS_H
#define METRICS_H

#include <stdbool.h>
#include <stdint.h>

/* Run-wide labels, written into every per-job record. */
typedef struct {
    const char *run_id;
    const char *mode;        /* "rtdra" | "vanilla" */
    const char *taskset_id;
    uint64_t budget_q_us;    /* label only (real enforcement is the RT-DRA claim) */
    uint64_t period_p_us;    /* label only */
    int cores_m;             /* label only */
    double util;
    int n_tasks;
    const char *interference; /* "none" | "on" */
    const char *node;
    const char *kernel;
} metrics_labels_t;

/* One job's outcome. */
typedef struct {
    int task_id;
    uint64_t job_index;
    uint64_t release_ts_ns;     /* relative to run epoch */
    uint64_t start_ts_ns;       /* relative to run epoch */
    uint64_t completion_ts_ns;  /* relative to run epoch */
    uint64_t exec_time_us;      /* thread CPU time consumed */
    uint64_t response_time_us;  /* completion - release (wall) */
    uint64_t target_c_us;
    uint64_t period_t_us;
    uint64_t deadline_us;
    bool overrun;               /* exec_time_us > target_c_us */
    bool deadline_miss;         /* completion > release + deadline */
    uint64_t tardiness_us;      /* max(0, completion - (release + deadline)) */
} job_record_t;

int metrics_open(const char *path, const metrics_labels_t *labels);
void metrics_write(const job_record_t *rec);
void metrics_flush(void);
void metrics_close(void);

#endif /* METRICS_H */
