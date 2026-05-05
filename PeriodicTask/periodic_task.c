#define _POSIX_C_SOURCE 200112L
#include <unistd.h>
#include <getopt.h>
#include <stdlib.h>
#include <inttypes.h>
#include <stdio.h>


#include "rt_utils.h"
#include "gettime.h"
#include "cputime.h"
#include "cpu_consume.h"
#include "task.h"
#include "output.h"

#define MAX_N 1000
unsigned int N = MAX_N;
static uint64_t times[MAX_N];
static uint64_t mytimes[MAX_N];
static uint64_t start_time;

#define Q     15000
#define P    100000
#define CMIN  10000
#define CMAX  10000
#define T    100000
int args_parse(int argc, char *argv[], struct task_p *p)
{
  int v;

  p->max_budget = Q;
  p->cbs_period = P;
  p->cbs_flags  = 0;
  p->prio       = 0;
  p->bcet = CMIN;
  p->wcet = CMAX;
  p->period = T;
  p->offset = 500 * 1000;
  while((v = getopt(argc, argv, "N:R:q:t:p:C:c:r:P:f:")) != -1) {
    switch(v) {
      case 'q':
        p->max_budget = atoi(optarg);
        printf("#Q = %d\n", p->max_budget);
        break;
      case 't':
        p->cbs_period = atoi(optarg);
        printf("#Server Period = %d\n", p->cbs_period);
        break;
      case 'f':
        p->cbs_flags = atoi(optarg);
        printf("#Server Period = %d\n", p->cbs_flags);
        break;
      case 'p':
        p->period = atoi(optarg);
        printf("#T = %d\n", p->period);
        break;
      case 'C':
        p->bcet = p->wcet = atoi(optarg);
        printf("#Fixed C = %d\n", p->wcet);
        break;
      case 'c':
        sscanf(optarg, "%d/%d", &p->bcet, &p->wcet);
        printf("#Uniform C = [%d, %d]\n", p->bcet, p->wcet);
        break;
      case 'r':
        p->offset = atoi(optarg);
        printf("#Offset: %d\n", p->offset);
        break;
      case 'N':
        N = atoi(optarg);
        if (N > MAX_N) N = MAX_N;
        break;
      case 'R':
        cnt = atoi(optarg);
        break;
      case 'P':
        p->prio = atoi(optarg);
        break;
      default:
        fprintf(stderr, "Exiting because of illegal option!\n");

        exit(-1);
    }
  }

  return 1;
}

int main(int argc, char *argv[])
{
  struct task_p param;

  args_parse(argc, argv, &param);
  make_rt(1);
  
  if (cnt == 0) {
    uint64_t hz;

    hz = cpu_speed();
    printf("#CPU Speed: %"PRIu64"\n", hz);
    cnt = calibrate(calib_len / hz);
  }

  start_time = gettime() + param.offset;
  param.h = start_periodic_timer(param.offset, param.period);
  if (param.h == NULL) {
    perror("Start Periodic Timer");

    return -1;
  }
  param.times      = times;
  param.mytimes    = mytimes;

  printf("#PID: %u\n", getpid());
  printf("#Cycles: %"PRIu64"\n", cnt);

  task_body(&param);

  printf("#Start: %"PRIu64"\n", start_time);
  print_results(times, mytimes, start_time, 0, param.period, N);

  return 0;
}
