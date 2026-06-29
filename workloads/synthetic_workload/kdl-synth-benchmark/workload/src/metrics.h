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
    uint64_t wait_time_us;      /* response - exec: ready-but-off-CPU (supply/G1) */
    uint64_t preempt_us;        /* off-CPU time during the burn (pure starvation) */
    uint64_t target_c_us;
    uint64_t period_t_us;
    uint64_t deadline_us;
    bool overrun;               /* exec_time_us > target_c_us (demand inflation/G2) */
    bool deadline_miss;         /* completion > release + deadline */
    uint64_t tardiness_us;      /* max(0, completion - (release + deadline)) */
} job_record_t;

/* One run-level summary record, written once after all jobs complete. */
typedef struct {
    double steal_pct;       /* % of CPU stolen by the host over the run (G1) */
    uint64_t steal_us;      /* stolen CPU time over the run (us) */
    uint64_t wall_us;       /* run wall duration (us) */
    double iters_per_us;    /* busy-loop calibration */
    int n_tasks;
} metrics_summary_t;

int metrics_open(const char *path, const metrics_labels_t *labels);
void metrics_write(const job_record_t *rec);
void metrics_write_summary(const metrics_summary_t *s);
void metrics_flush(void);
void metrics_close(void);

#endif /* METRICS_H */
