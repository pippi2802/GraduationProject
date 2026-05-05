#include <inttypes.h>
#include <stdio.h>

#include "rt_utils.h"
#include "gettime.h"
#include "cpu_consume.h"
#include "sim_rand.h"
#include "task.h"

uint64_t cnt;
uint64_t calib_len = 100000;

static void job_body(uint64_t c)
{
  consume(c);
}

void *task_body(void *param)
{
  struct periodic_task *h;
  int cbs_period, cbs_flags, max_budget, wcet, bcet;
  uint64_t *times, *mytimes;
  struct task_p *tp = param;
  int prio;
  unsigned int i = 0;
  
  h          = tp->h;
  max_budget = tp->max_budget;
  cbs_period = tp->cbs_period;
  cbs_flags  = tp->cbs_flags;
  wcet       = tp->wcet;
  bcet       = tp->bcet;
  times      = tp->times;
  mytimes    = tp->mytimes;
  prio       = tp->prio;

  if (prio) {
    if (make_rt(prio) < 0) {
      fprintf(stderr, "Cannot set RT priority %d\n", prio);
    }
  } else {
    if (sched_set(max_budget, cbs_period, cbs_flags) < 0) {
      fprintf(stderr, "Cannot set (%d, %d) reservation!\n", max_budget, cbs_period);
    }
  }

  while(1) {
    uint64_t c;
    uint64_t t2;
    uint64_t t1mine, t2mine;

    wait_next_activation(h);
    t1mine = getmytime();
    if (wcet == bcet) {
      c = cnt * wcet / calib_len;
    } else {
      c = cnt * UNIF(bcet, wcet) / calib_len;
    }
    job_body(c);
    t2 = gettime();
    t2mine = getmytime();
#if 0
    printf("%Lu\n", t2 - t1);
#else
//    times[i++] = t2 - t1;
    mytimes[i] = t2mine - t1mine;
    times[i++] = t2;
    if (i == N) {
      return NULL;
    }
#endif
  }

  return NULL;
}


