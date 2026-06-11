#ifndef TASK_H
#define TASK_H

#include <stdint.h>

/* Per-task thread arguments. One periodic task = (C, T, D=T). */
typedef struct {
    int id;
    uint64_t c_us;          /* execution budget per job (target CPU time) */
    uint64_t t_us;          /* period */
    uint64_t d_us;          /* relative deadline (= t_us, implicit) */
    uint64_t jobs;          /* measured jobs (after warmup) */
    uint64_t warmup;        /* warmup jobs (not recorded) */
    double iters_per_us;    /* busy-loop calibration */
    uint64_t epoch_ns;      /* shared run epoch (CLOCK_MONOTONIC) */
    uint64_t start_at_ns;   /* absolute monotonic time of first release */
} task_arg_t;

/* pthread entry point: runs the absolute-time periodic loop. */
void *task_thread(void *arg);

#endif /* TASK_H */
