#define _POSIX_C_SOURCE 200112L
#include <sys/mman.h>
#include <sys/time.h>
#include <sched.h>
#include <time.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "rt_utils.h"
#include "dl_syscalls.h"

struct periodic_task {
        struct timespec r;
        int period;
};

#define NSEC_PER_SEC 1000000000ULL
static inline void timespec_add_us(struct timespec *t, uint64_t d)
{
    d *= 1000;
    d += t->tv_nsec;
    while (d >= NSEC_PER_SEC) {
        d -= NSEC_PER_SEC;
	t->tv_sec += 1;
    }
    t->tv_nsec = d;
}

void set_next_interarrival(struct periodic_task *t, int p)
{
  t->period = p;
}
void wait_next_activation(struct periodic_task *t)
{
    clock_nanosleep(CLOCK_REALTIME, TIMER_ABSTIME, &t->r, NULL);
    timespec_add_us(&t->r, t->period);
}

struct periodic_task *start_periodic_timer(uint64_t offs, int p)
{
    struct periodic_task *t;

    t = malloc(sizeof(struct periodic_task));
    if (t == NULL) {
        return NULL;
    }
    clock_gettime(CLOCK_REALTIME, &t->r);
    timespec_add_us(&t->r, offs);
    t->period = p;

    return t;
}

struct periodic_task *synch_periodic_timer(const struct periodic_task *t, int p)
{
    struct periodic_task *t1;

    t1 = malloc(sizeof(struct periodic_task));
    if (t1 == NULL) {
        return NULL;
    }
    memcpy(t1, t, sizeof(struct periodic_task));
    set_next_interarrival(t1, p);

    return t1;
}

int make_rt(int p)
{
  int res;
  struct sched_param param;

  param.sched_priority = p;
  res = sched_setscheduler (0, SCHED_FIFO, &param);
  if (res != 0) {
    perror ("sched_setscheduler");
    printf ("You probably need to be running as root --- SCHED_FIFO %d.\n", p);

    return -1;
  }
  res = mlockall(MCL_FUTURE);
  if (res < 0) {
    perror("MLockAll");
  }

  return 0;
}

int sched_set(uint32_t q, uint32_t t, uint32_t flags)
{
  struct sched_attr attr;

  attr.size = sizeof(struct sched_attr);
  attr.sched_flags = flags;
  attr.sched_policy = SCHED_DEADLINE;
  attr.sched_priority = 0;
  attr.sched_runtime  = q * 1000ULL;
  attr.sched_period   = t * 1000ULL;
  attr.sched_deadline = attr.sched_period;
  
  return sched_setattr(0, &attr, 0);
}

